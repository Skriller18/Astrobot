"""Tier 1 -- storing. Did the right facts get kept, and the wrong ones refused?"""
from harness import load, pct          # noqa: I001 - sets sys.path, must import first

import constants as C                    # noqa: E402
import utils as u                        # noqa: E402
from modules.memory.policy import evaluate  # noqa: E402


def run(cfg=None):
    data = load("a")
    rows, wrong = [], []

    for r in data["simple"]:
        msg, want = r["message"], r["decision"]
        # The extractor is an LLM; here we feed the labelled candidate directly so
        # this tier measures the GATE and the SCORE, not the extractor's parsing.
        cand = [{"type": r["type"], "value": " ".join(u.tokens(msg)[:6]),
                 "topic": r["topic"], "confidence": 0.85}]
        got = evaluate(cand, msg, [])
        action = got[0]["action"] if got else "DISCARD"
        kept = action != "DISCARD"
        ok = kept == (want == "STORE")
        rows.append({"message": msg, "expected": want, "got": action,
                     "score": got[0]["score"] if got else None, "ok": ok})
        if not ok:
            wrong.append({"message": msg, "expected": want, "got": action,
                          "score": got[0]["score"] if got else None,
                          "type": r["type"], "topic": r["topic"],
                          "parts": got[0]["parts"] if got else {},
                          "reason": got[0]["reason"] if got else ""})

    conflicts = []
    for c in data["conflict"]:
        existing = [{"id": "x", "type": c["existing"]["type"], "value": c["existing"]["value"],
                     "topic": c["existing"]["topic"], "confidence": 0.9,
                     "embedding": u.embed(c["existing"]["value"])}]
        got = evaluate([{**c["candidate"], "confidence": 0.9}], c["message"], existing)
        action = got[0]["action"] if got else "DISCARD"
        # CREATE and COEXIST are the same outcome: a new node is added alongside.
        same = {"CREATE", "COEXIST"}
        ok = action == c["expected"] or {action, c["expected"]} <= same
        conflicts.append({"message": c["message"], "expected": c["expected"],
                          "got": action, "ok": ok, "why": c["why"]})

    correct = sum(r["ok"] for r in rows)
    junk = sum(1 for r in rows if r["expected"] == "DISCARD" and r["got"] != "DISCARD")
    missed = sum(1 for r in rows if r["expected"] == "STORE" and r["got"] == "DISCARD")
    return {
        "tier": 1, "name": "storing",
        "config": {"PROMOTION_THRESHOLD": C.PROMOTION_THRESHOLD,
                   "PROMOTION_WEIGHTS": dict(C.PROMOTION_WEIGHTS)},
        "metrics": {
            "accuracy_pct": pct(correct, len(rows)),
            "junk_stored": junk,                 # counter-metric: must stay near 0
            "facts_missed": missed,
            "conflict_accuracy_pct": pct(sum(c["ok"] for c in conflicts), len(conflicts)),
            "n": len(rows),
        },
        "failures": wrong, "conflicts": conflicts, "rows": rows,
    }
