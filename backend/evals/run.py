"""Run the eval suite and write JSON results for the dashboard.

    python evals/run.py            # tiers 1-3 + sweep  (offline, free, seconds)
    python evals/run.py --full     # adds tier 3 on a real model and tier 4  (paid)
"""
import argparse, datetime, json, sys, time

from harness import RESULTS, save          # noqa: I001 - sets sys.path first

import sweep, tier1, tier2, tier3          # noqa: E402


def stamp():
    return datetime.datetime.now().isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="include real-model tiers 3 and 4")
    ap.add_argument("--limit", type=int, default=None, help="cap tier 4 questions")
    args = ap.parse_args()

    out, t0 = {"generated_at": stamp(), "tiers": {}}, time.time()

    # Tier 4 costs ~11 minutes of API calls. A cheap offline re-run (no --full) keeps
    # the existing one rather than silently dropping it from the dashboard.
    prev_path = RESULTS / "latest.json"
    if prev_path.exists() and not args.full:
        prev = json.loads(prev_path.read_text())
        for k in ("tier3_real", "tier4"):
            if k in prev.get("tiers", {}):
                out["tiers"][k] = prev["tiers"][k]
                out[f"{k}_carried_from"] = prev.get("generated_at")

    def checkpoint():
        """Save after every tier: a failure late in the run must not discard
        the tiers that already succeeded."""
        out["duration_s"] = round(time.time() - t0, 1)
        save("latest", out)

    print("tier 1  storing ...", flush=True)
    out["tiers"]["tier1"] = tier1.run()
    print("  ", json.dumps(out["tiers"]["tier1"]["metrics"]))
    checkpoint()

    print("tier 2  retrieval ...", flush=True)
    out["tiers"]["tier2"] = tier2.run()
    print("  ", json.dumps(out["tiers"]["tier2"]["metrics"]))
    checkpoint()

    print("tier 3  conversations (mock) ...", flush=True)
    out["tiers"]["tier3_mock"] = tier3.run(provider="mock")
    print("  ", json.dumps(out["tiers"]["tier3_mock"]["metrics"]))
    checkpoint()

    print("sweep   static constants ...", flush=True)
    out["sweep"] = sweep.run()
    print(f"   {len(out['sweep']['runs'])} configurations scored")
    checkpoint()

    if args.full:
        print("tier 3  conversations (gemini-3.8-flash) ...", flush=True)
        real = tier3.run(provider="gemini", model="gemini-3.8-flash")
        out["tiers"]["tier3_real"] = real
        print("  ", json.dumps(real["metrics"]))
        checkpoint()

        print("tier 4  quality: 4 models x brain on/off, judged ...", flush=True)
        import tier4
        try:
            out["tiers"]["tier4"] = tier4.run(limit=args.limit, seeded=real)
            print("  ", json.dumps(out["tiers"]["tier4"]["metrics"]["advice_on_vs_off"]))
        except Exception as e:                   # noqa: BLE001
            out["tier4_error"] = str(e)[:300]
            print("   tier 4 failed:", str(e)[:200])
        checkpoint()

    out["duration_s"] = round(time.time() - t0, 1)
    path = save("latest", out)
    save(f"run-{datetime.datetime.now():%Y%m%d-%H%M%S}", out)
    print(f"\nwrote {path}  ({out['duration_s']}s)")


if __name__ == "__main__":
    sys.exit(main())
