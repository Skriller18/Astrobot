"""Tier 2 -- retrieval. Were the right memories picked, and was silence chosen
when nothing was relevant?"""
from harness import load, pct, seeded_brain   # noqa: I001 - sets sys.path first

import constants as C                    # noqa: E402
import utils as u                        # noqa: E402
from modules.brain import retrieval      # noqa: E402


def run(cfg=None):
    brain, user = seeded_brain()
    memories = brain.active_memories(user)
    rows, tp = [], 0
    total_expected = total_selected = 0
    silence_right = silence_total = 0

    for q in load("b")["queries"]:
        question, expect = q["question"], set(q["expect"])
        topics = u.classify_topics(question)
        followup = u.is_followup(question, [])
        kept = [] if followup else retrieval.select(question, memories, topics)[0]
        got = {k["id"] for k in kept}

        hit = len(got & expect)
        tp += hit
        total_expected += len(expect)
        total_selected += len(got)
        if not expect:
            silence_total += 1
            silence_right += int(not got)

        rows.append({"question": question, "topics": topics, "followup": followup,
                     "expected": sorted(expect), "got": sorted(got),
                     "missed": sorted(expect - got), "extra": sorted(got - expect),
                     "ok": got == expect})

    return {
        "tier": 2, "name": "retrieval",
        # id -> human-readable, so the dashboard can show "switch jobs next year"
        # instead of "m_goal_switch".
        "memories": {m["id"]: {"value": m["value"], "type": m["type"], "topic": m["topic"]}
                     for m in load("b")["seed"]},
        "config": {"RETRIEVAL_FLOOR": C.RETRIEVAL_FLOOR, "TOP_K": C.TOP_K,
                   "COSINE_BAND": list(C.COSINE_BAND)},
        "metrics": {
            "precision_pct": pct(tp, total_selected),
            "recall_pct": pct(tp, total_expected),
            "exact_match_pct": pct(sum(r["ok"] for r in rows), len(rows)),
            "correct_silence": f"{silence_right}/{silence_total}",
            "avg_injected": round(total_selected / len(rows), 2),   # operational metric
            "n": len(rows),
        },
        "rows": rows,
    }
