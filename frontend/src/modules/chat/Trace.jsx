"use client";

const pct = (n) => `${Math.round(n * 100)}%`;

function Bar({ value, label }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <span className="bar-track"><span className="bar-fill" style={{ width: pct(value) }} /></span>
      <span className="bar-value">{value.toFixed(2)}</span>
    </div>
  );
}

/** Renders the six pipeline steps the backend traced, so the maths is visible. */
export default function Trace({ trace }) {
  if (!trace) return null;
  const find = (name) => trace.steps.find((s) => s.step === name) || {};
  const understand = find("understand"), retrieve = find("retrieve");
  const prompt = find("build_prompt"), llm = find("llm"), memory = find("update_memory");

  return (
    <aside className="trace">
      <h3>Underneath the response</h3>

      <section>
        <h4>1 · Understand</h4>
        <p>Topics: <b>{understand.topics?.join(", ") || "none detected"}</b></p>
        <p>Follow-up: <b>{String(understand.is_followup)}</b> (score {understand.followup_score})</p>
      </section>

      <section>
        <h4>2 · Retrieve</h4>
        {retrieve.skipped ? (
          <p className="muted">Skipped — {retrieve.reason}</p>
        ) : retrieve.candidates?.length ? (
          <>
            <p className="muted">score = relevance × confidence × importance × decay</p>
            {retrieve.candidates.map((c) => (
              <div key={c.id} className={`cand ${c.included ? "in" : "out"}`}>
                <div className="cand-head">
                  <span>{c.value}</span>
                  <b>{c.score.toFixed(3)}</b>
                </div>
                <div className="cand-math">
                  {c.relevance} × {c.confidence} × {c.importance} × {c.decay}
                  {c.included ? " · used" : ` · below floor ${retrieve.floor}`}
                </div>
              </div>
            ))}
          </>
        ) : (
          <p className="muted">No memories stored yet.</p>
        )}
      </section>

      <section>
        <h4>3 · Build prompt</h4>
        <p>~{prompt.approx_tokens} tokens · {prompt.memories_included} memories ·{" "}
          {prompt.history_turns} prior turns</p>
      </section>

      <section>
        <h4>4 · Generate</h4>
        <p>{llm.provider || "unavailable"} · {llm.model || "—"}</p>
        {llm.degraded && <p className="warn">Degraded — all providers failed</p>}
        {!!llm.fallbacks_tried?.length && (
          <p className="muted">Fell through: {llm.fallbacks_tried.join(", ")}</p>
        )}
      </section>

      <section>
        <h4>5 · Remember</h4>
        {memory.decisions?.length ? (
          memory.decisions.map((d, i) => (
            <div key={i} className="decision">
              <div className="cand-head">
                <span>{d.value}</span>
                <b className={d.action === "DISCARD" ? "discard" : "keep"}>{d.action}</b>
              </div>
              <p className="muted">{d.reason}</p>
              {Object.entries(d.parts).map(([k, v]) => <Bar key={k} label={k} value={v} />)}
              <Bar label="promotion" value={d.score} />
              <p className="muted">threshold {memory.threshold}</p>
            </div>
          ))
        ) : (
          <p className="muted">Nothing durable in this message.</p>
        )}
      </section>
    </aside>
  );
}
