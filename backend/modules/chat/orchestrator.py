"""The six-step flow: understand -> retrieve -> build -> call -> reply -> remember.

`prepare` covers steps 1-3 and `finalize` covers 5-6, so the blocking and the
streaming entry points run exactly the same pipeline with only step 4 differing.
"""
import constants as C
import utils as u
from modules.brain import retrieval
from modules.chat import prompts
from modules.llm.base import LLMError
from modules.llm.registry import complete, stream
from modules.memory import extractor, policy

FALLBACK_REPLY = ("I am having trouble reaching my reasoning engine right now. "
                  "Please try again in a moment.")


def prepare(message, user_id, session_id, brain, sessions):
    """Steps 1-3. Everything needed to call the LLM, plus the trace so far."""
    trace = {"steps": []}
    step = lambda name, **d: trace["steps"].append({"step": name, **d})

    user = brain.get_user(user_id) or brain.upsert_user(user_id)
    history = sessions.last_turns(session_id)
    recent = [t["content"] for t in history]
    topics = u.classify_topics(message)
    followup = u.is_followup(message, recent)
    step("understand", topics=topics, is_followup=followup,
         followup_score=round(u.followup_score(message, recent), 3),
         history_turns=len(history))

    if followup:
        kept, scored = [], []
        step("retrieve", skipped=True,
             reason="follow-up question: the conversation window already has the answer")
    else:
        memories = brain.active_memories(user_id)
        kept, scored = retrieval.select(message, memories, topics)
        step("retrieve", candidates=scored, selected=[k["id"] for k in kept],
             floor=C.RETRIEVAL_FLOOR, top_k=C.TOP_K,
             reason=("no memory cleared the relevance floor"
                     if memories and not kept else f"{len(kept)} of {len(memories)} memories used"))

    msgs, budget = prompts.build(user, kept, history, message)
    step("build_prompt", **budget)
    return {"user": user, "kept": kept, "msgs": msgs, "trace": trace,
            "missing": prompts.missing_profile(user)}


def finalize(ctx, text, degraded, message, user_id, session_id, brain, sessions,
             provider=None, model=None):
    """Steps 5-6: persist the turn, then decide what deserves remembering."""
    step = lambda name, **d: ctx["trace"]["steps"].append({"step": name, **d})

    sessions.add_turn(session_id, user_id, "user", message)
    sessions.add_turn(session_id, user_id, "assistant", text)

    cands, err = extractor.extract(message, provider=provider, model=model)
    decisions = policy.evaluate(cands, message, brain.active_memories(user_id))
    applied = policy.apply(decisions, brain, user_id, message, session_id)
    step("update_memory", candidates=len(cands), decisions=decisions,
         applied=[a["action"] for a in applied], threshold=C.PROMOTION_THRESHOLD,
         extraction_error=err)

    return {
        "response": text, "user_id": user_id, "session_id": session_id,
        "context_used": [k["value"] for k in ctx["kept"]]
                        + (["user_profile"] if ctx["user"].get("name") else []),
        "degraded": degraded, "brain": brain.kind, "sessions": sessions.kind,
        "missing_profile": ctx["missing"], "trace": ctx["trace"],
    }


def _with_missing(text, missing, degraded):
    if missing and not degraded:
        return text + f"\n\nTo read your chart properly I still need your {', '.join(missing)}."
    return text


def handle(message, user_id, session_id, brain, sessions, provider=None, model=None):
    """Blocking: the whole reply is built before anything is returned."""
    ctx = prepare(message, user_id, session_id, brain, sessions)
    step = lambda name, **d: ctx["trace"]["steps"].append({"step": name, **d})

    try:
        resp, tried = complete(ctx["msgs"], provider=provider, model=model)
        text, degraded, used = resp.text, False, {"provider": resp.provider, "model": resp.model}
    except LLMError as e:
        text, degraded, tried = FALLBACK_REPLY, True, [str(e)[:120]]
        used = {"provider": None, "model": None}
    step("llm", **used, fallbacks_tried=tried, degraded=degraded)

    text = _with_missing(text, ctx["missing"], degraded)
    return finalize(ctx, text, degraded, message, user_id, session_id, brain, sessions,
                    provider, model)


def handle_stream(message, user_id, session_id, brain, sessions, provider=None, model=None):
    """Streaming: yields ("context", ...), ("token", ...)*, then ("done", payload).

    The context event carries steps 1-3, so the UI can show retrieval scoring
    before the first token lands.
    """
    ctx = prepare(message, user_id, session_id, brain, sessions)
    step = lambda name, **d: ctx["trace"]["steps"].append({"step": name, **d})
    yield "context", {"steps": list(ctx["trace"]["steps"])}

    parts, degraded, used, tried = [], False, {"provider": None, "model": None}, []
    try:
        for kind, payload in stream(ctx["msgs"], provider=provider, model=model):
            if kind == "meta":
                used = {"provider": payload["provider"], "model": payload["model"]}
                tried = payload["fallbacks_tried"]
            elif kind == "token":
                parts.append(payload)
                yield "token", payload
            else:                                # mid-stream failure, partial text kept
                degraded, tried = True, tried + [payload]
    except LLMError as e:
        degraded, tried = True, [str(e)[:120]]

    text = "".join(parts) or FALLBACK_REPLY
    step("llm", **used, fallbacks_tried=tried, degraded=degraded, streamed=True)

    tail = _with_missing("", ctx["missing"], degraded)
    if tail:
        yield "token", tail
    yield "done", finalize(ctx, text + tail, degraded, message, user_id, session_id,
                           brain, sessions, provider, model)
