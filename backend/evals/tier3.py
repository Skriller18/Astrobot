"""Tier 3 -- conversations. Do the assignment's scenarios still behave correctly?

Runs on the mock provider so it is deterministic and free. Also captures the
answers flagged `judge: true`, which Tier 4 scores for quality.
"""
from harness import load                     # noqa: I001 - sets sys.path first

import constants as C                        # noqa: E402
from modules.brain.store import MemoryBrain  # noqa: E402
from modules.chat.orchestrator import handle  # noqa: E402
from modules.session.store import MemorySessions  # noqa: E402


def _check(result, brain, user, before, expect):
    step = {s["step"]: s for s in result["trace"]["steps"]}
    got = {
        "stored": len(brain.active_memories(user)) > before,
        "retrieved": bool(step["retrieve"].get("selected")),
        "followup": step["understand"]["is_followup"],
        "missing_profile": bool(result["missing_profile"]),
    }
    return got, all(got[k] == v for k, v in expect.items())


def run(cfg=None, provider="mock", model=None):
    brain, sessions = MemoryBrain(), MemorySessions()
    scripts, judged, rows = load("c")["scripts"], [], []

    for script in scripts:
        user = script["user"]
        if script.get("profile"):
            brain.upsert_user(user, **script["profile"])
        elif not brain.get_user(user):
            brain.upsert_user(user)
        session = f"{script['id']}-s1"
        ok_all = True

        for i, turn in enumerate(script["turns"]):
            if script.get("new_session_before") == i:
                session = f"{script['id']}-s2"
            before = len(brain.active_memories(user))
            res = handle(turn["say"], user, session, brain, sessions,
                         provider=provider, model=model)
            got, ok = _check(res, brain, user, before, turn.get("assert", {}))
            ok_all &= ok
            rows.append({"script": script["id"], "turn": i, "say": turn["say"],
                         "expected": turn.get("assert", {}), "got": got, "ok": ok})
            if turn.get("judge"):
                judged.append({"script": script["id"], "user": user, "session": session,
                               "question": turn["say"],
                               "context_used": res["context_used"],
                               "history": [t["content"] for t in sessions.last_turns(session)][:-2]})

        rows[-1]["script_ok"] = ok_all

    passed = len({r["script"] for r in rows if r.get("script_ok")})
    return {
        "tier": 3, "name": "conversations",
        "config": {"provider": provider, "PROMOTION_THRESHOLD": C.PROMOTION_THRESHOLD,
                   "RETRIEVAL_FLOOR": C.RETRIEVAL_FLOOR},
        "metrics": {"scripts_passed": f"{passed}/{len(scripts)}",
                    "turns_passed": f"{sum(r['ok'] for r in rows)}/{len(rows)}"},
        "rows": rows, "judged": judged,
    }
