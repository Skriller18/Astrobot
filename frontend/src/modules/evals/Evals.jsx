"use client";
import { useEffect, useState } from "react";
import { api } from "@/modules/api/client";
import Datasets from "@/modules/evals/Datasets";

const pct = (n) => (typeof n === "number" ? `${n}%` : n ?? "—");

/** "run-20260921-143811" -> "21 Sep 14:38" */
function runLabel(id) {
  const m = id.match(/run-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/);
  if (!m) return id;
  const month = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+m[2] - 1];
  return `${+m[3]} ${month} ${m[4]}:${m[5]}`;
}

/** A memory shown as a readable chip instead of a raw id like "m_goal_switch". */
function Mem({ id, lookup, tone }) {
  const m = lookup?.[id];
  return (
    <span className={`chip chip-${tone || "plain"}`} title={m ? `${m.type} · ${m.topic || "no topic"}` : id}>
      {m ? m.value : id}
      {m && <em>{m.type.toLowerCase()}</em>}
    </span>
  );
}

function MemList({ ids, lookup, tone, empty = "nothing" }) {
  if (!ids?.length) return <span className="chip chip-none">{empty}</span>;
  return <span className="chips">{ids.map((id) => <Mem key={id} id={id} lookup={lookup} tone={tone} />)}</span>;
}

function Metric({ label, value, note, tone }) {
  return (
    <div className="metric">
      <span className={`metric-value ${tone || ""}`}>{value}</span>
      <span className="metric-label">{label}</span>
      {note && <span className="metric-note">{note}</span>}
    </div>
  );
}

function TierCard({ n, title, subtitle, question, children }) {
  return (
    <section className="card eval-tier">
      <header>
        <div className="row spread">
          <h3>{n ? `Tier ${n} · ${title}` : title}</h3>
          <span className="muted">{subtitle}</span>
        </div>
        {question && <p className="tier-q">{question}</p>}
      </header>
      {children}
    </section>
  );
}

/** Which value the sweep says is best: highest primary, ties broken by lower counter. */
function best(runs, constant) {
  const rows = runs.filter((r) => r.constant === constant);
  if (!rows.length) return null;
  return rows.reduce((a, b) => {
    if (b.primary !== a.primary) return b.primary > a.primary ? b : a;
    return Number(b.counter) < Number(a.counter) ? b : a;
  });
}

const EXPECT_WORDS = {
  stored: ["a memory was stored", "nothing was stored"],
  retrieved: ["memory was retrieved", "no memory was retrieved"],
  followup: ["treated as a follow-up", "not a follow-up"],
  missing_profile: ["asked for missing details", "profile was complete"],
};
const sayExpect = (e) =>
  Object.entries(e || {}).map(([k, v]) => EXPECT_WORDS[k]?.[v ? 0 : 1] ?? `${k}=${v}`).join(" · ") || "—";

export default function Evals() {
  const [data, setData] = useState(null);
  const [runs, setRuns] = useState([]);
  const [which, setWhich] = useState("latest");
  const [err, setErr] = useState(null);

  useEffect(() => { api.evalRuns().then(setRuns).catch(() => setRuns([])); }, []);
  useEffect(() => {
    setData(null); setErr(null);
    api.evals(which === "latest" ? undefined : which).then(setData).catch((e) => setErr(e.message));
  }, [which]);

  if (err) return <div className="profile"><p className="muted">No eval results yet — run <code>python evals/run.py --full</code>. ({err})</p></div>;

  const t = data?.tiers || {};
  const t1 = t.tier1, t2 = t.tier2, t3 = t.tier3_real || t.tier3_mock, t4 = t.tier4;
  const sweep = data?.sweep;
  const lookup = t2?.memories;

  return (
    <div className="evals-layout">
    <div className="profile evals">
      <div className="row spread eval-head">
        <div>
          <h2 className="eval-title">Evaluation</h2>
          <p className="muted">
            {data ? `${data.generated_at} · ${data.duration_s}s` : "loading…"} ·
            {" "}tiers 1–3 are deterministic and offline; tier 4 calls real models
          </p>
        </div>
        <label className="run-picker">
          Run
          <select value={which} onChange={(e) => setWhich(e.target.value)}>
            <option value="latest">latest</option>
            {runs.map((r) => <option key={r} value={r}>{runLabel(r)}</option>)}
          </select>
        </label>
      </div>

      {!data && <p className="muted">Loading…</p>}

      {/* ------------------------------------------------ tier 1 */}
      {t1 && (
        <TierCard n={1} title="Storing" subtitle={`${t1.metrics.n} labelled messages`}
                  question="Of the things the user said, did we keep the right ones and refuse the rest?">
          <div className="metrics">
            <Metric label="decisions correct" value={pct(t1.metrics.accuracy_pct)} />
            <Metric label="junk kept" value={t1.metrics.junk_stored} note="should be 0" tone={t1.metrics.junk_stored ? "warn" : ""} />
            <Metric label="real facts dropped" value={t1.metrics.facts_missed} tone={t1.metrics.facts_missed ? "warn" : ""} />
            <Metric label="corrections handled" value={pct(t1.metrics.conflict_accuracy_pct)} note="supersede vs coexist" />
          </div>
          {!!t1.failures?.length && (
            <>
              <h4>Where it got it wrong</h4>
              <table className="tbl">
                <thead><tr><th>the user said</th><th>we should have</th><th>we actually</th><th>score</th><th>why</th></tr></thead>
                <tbody>
                  {(t1.failures || []).map((f, i) => (
                    <tr key={i}>
                      <td>“{f.message}”</td>
                      <td>{f.expected === "STORE" ? "kept it" : "ignored it"}</td>
                      <td className="bad">{f.got === "DISCARD" ? "ignored it" : "kept it"}</td>
                      <td>{f.score ?? "—"} <span className="muted">/ 0.55</span></td>
                      <td className="muted">{f.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </TierCard>
      )}

      {/* ------------------------------------------------ tier 2 */}
      {t2 && (
        <TierCard n={2} title="Retrieval" subtitle={`${t2.metrics.n} labelled questions`}
                  question="When the user asks something, do we put the right memories in front of the model — and nothing else?">
          <div className="metrics">
            <Metric label="of what we fetched was right" value={pct(t2.metrics.precision_pct)} note="precision" />
            <Metric label="of what mattered we found" value={pct(t2.metrics.recall_pct)} note="recall" />
            <Metric label="questions exactly right" value={pct(t2.metrics.exact_match_pct)} />
            <Metric label="stayed silent correctly" value={t2.metrics.correct_silence}
                    note="when nothing was relevant" />
            <Metric label="memories per answer" value={t2.metrics.avg_injected} note="prompt cost" />
          </div>
          <table className="tbl tbl-mem">
            <thead><tr><th>question</th><th>should have used</th><th>actually used</th><th></th></tr></thead>
            <tbody>
              {(t2.rows || []).map((r, i) => (
                <tr key={i} className={r.ok ? "" : "row-bad"}>
                  <td>“{r.question}”</td>
                  <td><MemList ids={r.expected} lookup={lookup} tone="want" empty="nothing — correctly" /></td>
                  <td><MemList ids={r.got} lookup={lookup} tone="got" empty="nothing" /></td>
                  <td className="verdict">
                    {r.ok ? <span className="ok">exact</span> : (
                      <>
                        {!!r.extra?.length && <span className="bad">{r.extra.length} extra</span>}
                        {!!r.missed?.length && <span className="bad">{r.missed.length} missed</span>}
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted note">
            <b>extra</b> = a memory we injected that should not have been there (noise in the prompt).
            {" "}<b>missed</b> = a relevant memory we failed to surface.
          </p>
        </TierCard>
      )}

      {/* ------------------------------------------------ tier 3 */}
      {t3 && (
        <TierCard n={3} title="Conversations" subtitle={`answered by ${t3.config.provider}`}
                  question="Do the end-to-end scenarios from the brief still behave correctly?">
          <div className="metrics">
            <Metric label="scenarios passed" value={t3.metrics.scripts_passed} />
            <Metric label="turns passed" value={t3.metrics.turns_passed} />
          </div>
          {t.tier3_mock && t.tier3_real && (
            <p className="muted note">
              Mock provider scores {t.tier3_mock.metrics.scripts_passed}, a real model
              {" "}{t.tier3_real.metrics.scripts_passed}. <b>That gap is the stub extractor, not the system</b> —
              the mock only recognises keyword topics.
            </p>
          )}
          <table className="tbl">
            <thead><tr><th>scenario</th><th>the user said</th><th>we expected</th><th></th></tr></thead>
            <tbody>
              {(t3.rows || []).map((r, i) => (
                <tr key={i} className={r.ok ? "" : "row-bad"}>
                  <td className="mono">{r.script}</td>
                  <td>“{r.say}”</td>
                  <td className="muted">{sayExpect(r.expected)}</td>
                  <td className="verdict">{r.ok ? <span className="ok">pass</span> : <span className="bad">fail</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TierCard>
      )}

      {/* ------------------------------------------------ sweep */}
      {sweep && (
        <TierCard title="Choosing the numbers" subtitle={`${sweep.runs.length} configurations tried`}
                  question="For each constant, which value actually works best — and what does it cost?">
          <p className="muted note">
            One constant changes at a time. A value only wins if the <b>primary</b> metric improves
            <b> and</b> the <b>counter</b> metric does not get worse — otherwise we have just moved the
            problem somewhere else.
          </p>
          {Object.keys(sweep.grid).map((constant) => {
            const rows = sweep.runs.filter((r) => r.constant === constant);
            const win = best(sweep.runs, constant);
            const meaning = {
              PROMOTION_THRESHOLD: "how sure we must be before storing a fact",
              RETRIEVAL_FLOOR: "how relevant a memory must be before we use it",
              TOP_K: "how many memories we are willing to inject",
              PROMOTION_WEIGHTS: "how the four promotion signals are balanced",
            }[constant];
            return (
              <div key={constant} className="sweep-block">
                <h4>{constant} <span className="muted">— {meaning}</span></h4>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>value</th>
                      <th>{rows[0]?.primary_metric?.replace(/_/g, " ")}</th>
                      <th>{rows[0]?.counter_metric?.replace(/_/g, " ")} <span className="muted">(cost)</span></th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={i} className={r === win ? "row-best" : ""}>
                        <td className="mono">{r.value}</td>
                        <td>{r.primary}</td>
                        <td>{r.counter}</td>
                        <td className="verdict">
                          {r.is_current && <span className="tag-cur">in use</span>}
                          {r === win && <span className="tag-best">best</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </TierCard>
      )}

      {/* ------------------------------------------------ tier 4 */}
      {t4 && (
        <TierCard n={4} title="Answer quality"
                  subtitle={`pairs judged by ${t4.judge}${t4.rank_judge ? ` · ranking by ${t4.rank_judge}` : ""}`}
                  question="Does having the Shared Brain actually make the answer better — and which model answers best?">
          <div className="metrics">
            <Metric label="gave better advice" tone="good"
                    value={`${t4.metrics.advice_on_vs_off.on} vs ${t4.metrics.advice_on_vs_off.off}`}
                    note={`with brain vs without (${t4.metrics.advice_on_vs_off.tie} ties)`} />
            <Metric label="felt more personal"
                    value={`${t4.metrics.personalised_on_vs_off.on} vs ${t4.metrics.personalised_on_vs_off.off}`}
                    note={`(${t4.metrics.personalised_on_vs_off.tie} ties)`} />
            <Metric label="made facts up, with brain" value={t4.metrics.invented_facts_brain_on}
                    tone="good" note={`without brain: ${t4.metrics.invented_facts_brain_off}`} />
            <Metric label="control pairs"
                    value={`${t4.metrics.controls_advice.on}–${t4.metrics.controls_advice.off}–${t4.metrics.controls_advice.tie}`}
                    note="should be balanced, or judging is biased" />
          </div>
          <p className="muted note">
            Each pair is the <b>same question answered twice by the same model</b> — once with its
            memories, once without — shown to the judge blind and in random order.
          </p>

          <h4>Which model answers best</h4>
          <table className="tbl">
            <thead><tr><th>model</th><th>score</th><th>brain helped</th><th>felt personal</th><th>made things up</th></tr></thead>
            <tbody>
              {Object.entries(t4.metrics.model_rank_points || {}).map(([m, pts], i) => {
                const pm = t4.metrics.per_model[m] || {};
                return (
                  <tr key={m} className={i === 0 ? "row-best" : ""}>
                    <td className="mono">{m}{i === 0 && <span className="tag-best">top ranked</span>}</td>
                    <td><b>{pts}</b></td>
                    <td>{pm.advice ? `${pm.advice.on} of ${pm.advice.on + pm.advice.off + pm.advice.tie}` : "—"}</td>
                    <td>{pm.personalised ? `${pm.personalised.on} of ${pm.personalised.on + pm.personalised.off + pm.personalised.tie}` : "—"}</td>
                    <td className={pm.invented_on ? "bad" : "ok"}>{pm.invented_on ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="muted note">
            With only ~6 pairs per model these per-model numbers are noisy — the aggregate above is
            the reliable figure.
          </p>

          <h4>Every verdict</h4>
          <table className="tbl">
            <thead><tr><th>question</th><th>model</th><th>better advice</th><th>judge's reason</th></tr></thead>
            <tbody>
              {(t4.pairs || []).filter((p) => !p.error).map((p, i) => (
                <tr key={i} className={p.is_control ? "row-control" : ""}>
                  <td>“{p.question}”{p.is_control && <span className="tag-cur">control</span>}</td>
                  <td className="mono">{p.model}</td>
                  <td className={p.advice_winner === "on" ? "ok" : p.advice_winner === "off" ? "bad" : "muted"}>
                    {{ on: "with brain", off: "without brain", tie: "tie" }[p.advice_winner]}
                  </td>
                  <td className="muted">{p.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Read the answers yourself</h4>
          {(t4.generations || []).map((g, i) => (
            <details key={i}>
              <summary><span className="mono">{g.model}</span> — “{g.question}”</summary>
              <div className="gen-pair">
                <div><b className="ok">with brain</b>
                  <p className="muted small">knew: {g.context_used?.join(", ") || "nothing"}</p>
                  <p>{g.brain_on}</p></div>
                <div><b>without brain</b><p className="muted small">knew: nothing</p><p>{g.brain_off}</p></div>
              </div>
            </details>
          ))}
        </TierCard>
      )}
    </div>
    <Datasets />
    </div>
  );
}
