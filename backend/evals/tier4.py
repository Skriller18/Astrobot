"""Tier 4 -- response quality.

Two questions, deliberately separated:

  4a  Does the Shared Brain help?      brain ON vs brain OFF, same model, blind pairwise.
  4b  Which model answers best?        all four models ranked on the same brain-ON answers.

Judge is glm-5.3:cloud -- deliberately NOT one of the four candidates, so no model
is grading its own output.
"""
import json, random

from harness import config                    # noqa: I001 - sets sys.path first

import constants as C                         # noqa: E402
import tier3                                  # noqa: E402
from modules.brain.store import MemoryBrain   # noqa: E402
from modules.chat.orchestrator import handle  # noqa: E402
from modules.llm.registry import get_provider  # noqa: E402
from modules.session.store import MemorySessions  # noqa: E402

CANDIDATES = [("gemini", "gemini-3.8-flash"), ("gemini", "gemini-3.7-flash"),
              ("ollama", "deepseek-v4-flash:cloud"), ("ollama", "deepseek-v4.1-flash:cloud")]
# Two judges, chosen for two different jobs.
#
# 4a is a WITHIN-MODEL comparison: brain-on vs brain-off output from the same model.
# Self-preference bias -- a model favouring its own text over a rival's -- cannot apply
# when both candidates come from the same model, so a fast, reliable judge is the right
# trade even though it is also a candidate elsewhere. Measured: 4/4 at 1.6s/call.
#
# 4b RANKS THE FOUR MODELS against each other, where self-preference is exactly the risk.
# That needs a judge of an independent lineage, so it uses glm-5.3 despite being slower
# and flakier (measured 2/3 at 29s/call, hence the retries).
#
# The first run used glm-5.3 for everything and lost 19 of 32 verdicts to
# "thinking consumed the budget". Those failures were NOT random -- longer answers make it
# think longer -- so they biased the result toward short answers. glm-5.3-flash as a
# fallback measured 0/3 and was dropped.
PAIR_JUDGE = ("gemini", "gemini-3.8-flash")     # within-model, so self-preference is moot
RANK_JUDGE = ("ollama", "glm-5.3:cloud")        # independent lineage for model-vs-model
JUDGE_BUDGET = 4000
JUDGE_RETRIES = 3

# Questions with no stored memory behind them: brain ON and OFF should look the same.
# A lopsided result here means the judging is biased and the run is untrustworthy.
CONTROLS = {"What is my lucky number?",   # nothing stored bears on this
            "Why do you say that?"}       # follow-up: the graph is skipped either way

PAIR_PROMPT = """Two AI astrologers answered the same user question.

WHAT THE SYSTEM LEGITIMATELY KNOWS ABOUT THIS USER:
{known}

USER QUESTION: {q}

ANSWER A:
{a}

ANSWER B:
{b}

Judge them on two SEPARATE criteria. An answer can be more personalised yet be worse advice.

Return JSON only:
{{"advice": "A"|"B"|"tie",
  "personalised": "A"|"B"|"tie",
  "invented_a": true|false,
  "invented_b": true|false,
  "reason": "one short sentence"}}

"invented" means stating a fact about the user that is NOT in the known list above and NOT
in the question. Using a fact from the known list is correct, not invention."""

RANK_PROMPT = """Four AI astrologers answered the same user question.

USER QUESTION: {q}

{answers}

Rank them best to worst on how USEFUL the advice is to this user.

Return JSON only: {{"ranking": ["1","2","3","4"], "best_reason": "one short sentence"}}"""


def _judge(prompt, judge):
    """Call a judge with retries. Returns (verdict, model_used)."""
    last = None
    for provider, model in [judge] * JUDGE_RETRIES:
        try:
            raw = get_provider(provider, model).complete(
                [{"role": "user", "content": prompt}],
                temperature=0, max_tokens=JUDGE_BUDGET, json_mode=True).text
            return json.loads(raw[raw.find("{"):raw.rfind("}") + 1]), model
        except Exception as e:                   # noqa: BLE001
            last = e
    raise RuntimeError(f"all judges failed: {str(last)[:120]}")


def _known_block(brain, user, context_used):
    """Everything the system may legitimately state about this user."""
    u = brain.get_user(user) or {}
    lines = [f"- {k}: {v}" for k, v in
             (("name", u.get("name")), ("date of birth", u.get("dob")),
              ("birth place", u.get("birth_place")), ("zodiac sign", u.get("zodiac")),
              ("element", u.get("element"))) if v]
    lines += [f"- remembered: {c}" for c in context_used if c != "user_profile"]
    return "\n".join(lines) or "- nothing is known about this user yet"


def _answer(question, user, script_id, brain, sessions, provider, model, brain_on):
    """brain OFF = a floor nothing can clear, so no memory is ever injected."""
    floor = C.RETRIEVAL_FLOOR if brain_on else 99.0
    with config(RETRIEVAL_FLOOR=floor):
        r = handle(question, user, f"{script_id}-t4", brain, sessions,
                   provider=provider, model=model)
    return r["response"], r["context_used"]


def run(limit=None, seeded=None):
    # Build one populated brain from Set C using a real extractor. Seeding costs
    # ~2 minutes of API calls, so the runner passes in a cached Tier 3 result.
    seeded = seeded or tier3.run(provider="gemini", model="gemini-3.8-flash")
    questions = seeded["judged"][:limit] if limit else seeded["judged"]
    rng = random.Random(7)

    generations, pairs, ranks = [], [], []

    for q in questions:
        brain, sessions = MemoryBrain(), MemorySessions()
        brain.upsert_user(q["user"], name="Rahul", dob="1995-08-15", birth_place="Delhi")
        for c in q["context_used"]:
            if c != "user_profile":
                brain.add_memory(q["user"], "GOAL", c, "career", 0.9, "seed", "s")

        # Expand "user_profile" into the actual fields. Passing the literal token made
        # the judge count legitimate use of the user's name and sign as INVENTED --
        # the same class of bug as not passing a known list at all.
        known = _known_block(brain, q["user"], q["context_used"])
        on_answers = {}
        for provider, model in CANDIDATES:
            on, ctx = _answer(q["question"], q["user"], q["script"], brain, sessions,
                              provider, model, True)
            off, _ = _answer(q["question"], q["user"], q["script"], brain, sessions,
                             provider, model, False)
            on_answers[model] = on
            generations.append({"question": q["question"], "model": model,
                                "brain_on": on, "brain_off": off, "context_used": ctx})

            # --- 4a: blind pairwise, position randomised per item ---
            swap = rng.random() < 0.5
            a, b = (off, on) if swap else (on, off)
            try:
                v, judged_by = _judge(
                    PAIR_PROMPT.format(q=q["question"], a=a, b=b, known=known), PAIR_JUDGE)
            except Exception as e:                       # noqa: BLE001
                pairs.append({"question": q["question"], "model": model,
                              "error": str(e)[:120]})
                continue
            key = {"A": "off" if swap else "on", "B": "on" if swap else "off", "tie": "tie"}
            pairs.append({
                "question": q["question"], "model": model,
                "is_control": q["question"] in CONTROLS,
                "advice_winner": key.get(v.get("advice"), "tie"),
                "personalised_winner": key.get(v.get("personalised"), "tie"),
                "invented_on": v.get("invented_b" if swap else "invented_a", False),
                "invented_off": v.get("invented_a" if swap else "invented_b", False),
                "reason": v.get("reason", ""), "shown_as": "off/on" if swap else "on/off",
                "judged_by": judged_by,
            })

        # --- 4b: rank all four brain-ON answers for this question ---
        labels = list(on_answers)
        rng.shuffle(labels)
        block = "\n\n".join(f"ANSWER {i+1}:\n{on_answers[m]}" for i, m in enumerate(labels))
        try:
            v, _ = _judge(RANK_PROMPT.format(q=q["question"], answers=block), RANK_JUDGE)
            order = [labels[int(x) - 1] for x in v["ranking"] if x.isdigit()
                     and 1 <= int(x) <= len(labels)]
            ranks.append({"question": q["question"], "ranking": order,
                          "reason": v.get("best_reason", "")})
        except Exception as e:                           # noqa: BLE001
            ranks.append({"question": q["question"], "error": str(e)[:120]})

    return {"tier": 4, "name": "quality",
            "judge": PAIR_JUDGE[1], "rank_judge": RANK_JUDGE[1],
            "candidates": [m for _, m in CANDIDATES],
            "metrics": _aggregate(pairs, ranks),
            "pairs": pairs, "ranks": ranks, "generations": generations}


def _aggregate(pairs, ranks):
    good = [p for p in pairs if "error" not in p]
    real = [p for p in good if not p["is_control"]]
    ctrl = [p for p in good if p["is_control"]]
    tally = lambda rows, k: {w: sum(1 for r in rows if r[k] == w) for w in ("on", "off", "tie")}

    per_model = {}
    for m in {p["model"] for p in good}:
        rows = [p for p in real if p["model"] == m]
        per_model[m] = {"advice": tally(rows, "advice_winner"),
                        "personalised": tally(rows, "personalised_winner"),
                        "invented_on": sum(1 for r in rows if r["invented_on"])}

    points = {}
    for r in ranks:
        for i, m in enumerate(r.get("ranking", [])):
            points[m] = points.get(m, 0) + (len(r["ranking"]) - i)

    return {
        "advice_on_vs_off": tally(real, "advice_winner"),
        "personalised_on_vs_off": tally(real, "personalised_winner"),
        "invented_facts_brain_on": sum(1 for r in real if r["invented_on"]),
        "invented_facts_brain_off": sum(1 for r in real if r["invented_off"]),
        "controls_advice": tally(ctrl, "advice_winner"),
        "per_model": per_model,
        "model_rank_points": dict(sorted(points.items(), key=lambda x: -x[1])),
        "judged_pairs": len(real), "control_pairs": len(ctrl),
        "judge_errors": len(pairs) - len(good),
    }
