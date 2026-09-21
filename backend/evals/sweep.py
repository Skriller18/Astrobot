"""Sweep the four static constants and record every configuration's scores.

One constant varies at a time -- change two and you cannot attribute the result.
"""
from harness import config                   # noqa: I001 - sets sys.path first

import constants as C                        # noqa: E402
import tier1, tier2                          # noqa: E402

GRID = {
    "PROMOTION_THRESHOLD": [0.50, 0.55, 0.60, 0.65, 0.70],
    "RETRIEVAL_FLOOR": [0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
    "TOP_K": [3, 4, 6, 8],
    "PROMOTION_WEIGHTS": [
        {"durability": 0.35, "specificity": 0.25, "utility": 0.25, "extraction": 0.15},
        {"durability": 0.25, "specificity": 0.25, "utility": 0.35, "extraction": 0.15},
        {"durability": 0.40, "specificity": 0.20, "utility": 0.25, "extraction": 0.15},
        {"durability": 0.25, "specificity": 0.25, "utility": 0.25, "extraction": 0.25},
    ],
}
# Which tier each constant is scored by, and the metric pair that decides it.
AFFECTS = {
    "PROMOTION_THRESHOLD": ("tier1", "accuracy_pct", "junk_stored"),
    "PROMOTION_WEIGHTS":   ("tier1", "accuracy_pct", "junk_stored"),
    "RETRIEVAL_FLOOR":     ("tier2", "exact_match_pct", "avg_injected"),
    "TOP_K":               ("tier2", "exact_match_pct", "avg_injected"),
}


def run():
    baseline = {"tier1": tier1.run(), "tier2": tier2.run()}
    runs = []
    for const, values in GRID.items():
        tier, primary, counter = AFFECTS[const]
        for v in values:
            with config(**{const: v}):
                res = tier1.run() if tier == "tier1" else tier2.run()
            runs.append({
                "constant": const,
                "value": v if not isinstance(v, dict) else "/".join(f"{x:.2f}" for x in v.values()),
                "raw_value": v, "tier": tier,
                "primary_metric": primary, "primary": res["metrics"][primary],
                "counter_metric": counter, "counter": res["metrics"][counter],
                "metrics": res["metrics"],
                "is_current": v == getattr(C, const),
            })
    return {"baseline": {k: v["metrics"] for k, v in baseline.items()}, "runs": runs,
            "grid": {k: [str(x) for x in v] for k, v in GRID.items()}}
