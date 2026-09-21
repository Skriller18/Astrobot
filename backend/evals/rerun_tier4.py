"""Re-run only tier 4 and merge it into latest.json (tiers 1-3 are unchanged)."""
import json, time

from harness import RESULTS, save          # noqa: I001 - sets sys.path first

import tier3, tier4                        # noqa: E402

t0 = time.time()
out = json.loads((RESULTS / "latest.json").read_text())

print("re-seeding from tier 3 (gemini-3.8-flash) ...", flush=True)
real = out["tiers"].get("tier3_real") or tier3.run(provider="gemini", model="gemini-3.8-flash")
out["tiers"]["tier3_real"] = real

print("tier 4 with hardened judge ...", flush=True)
out["tiers"]["tier4"] = tier4.run(seeded=real)
m = out["tiers"]["tier4"]["metrics"]
print("  advice on/off/tie:", m["advice_on_vs_off"], "| judge errors:", m["judge_errors"],
      "| pairs:", m["judged_pairs"], flush=True)

out["tier4_rerun_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
save("latest", out)
print(f"done in {time.time()-t0:.0f}s", flush=True)
