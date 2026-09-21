"use client";
import { useEffect, useState } from "react";
import { api } from "@/modules/api/client";

/** The golden data the evals actually run against, so the numbers are inspectable. */
const TABS = [
  { key: "a", tier: "Tier 1", title: "Messages", blurb: "Every message, and what should happen to it." },
  { key: "b", tier: "Tier 2", title: "Questions", blurb: "A fixed brain, and which memories each question should surface." },
  { key: "c", tier: "Tier 3", title: "Conversations", blurb: "Multi-turn scripts with an expected behaviour per turn." },
  { key: "rules", tier: "", title: "Rules", blurb: "Written before the labels, so a disagreement is about the rule." },
];

const EXPECT_WORDS = {
  stored: ["stores a memory", "stores nothing"],
  retrieved: ["retrieves a memory", "retrieves nothing"],
  followup: ["is a follow-up", "is not a follow-up"],
  missing_profile: ["asks for missing details", "profile complete"],
};

export default function Datasets() {
  const [d, setD] = useState(null);
  const [tab, setTab] = useState("a");
  const [q, setQ] = useState("");

  useEffect(() => { api.evalDatasets().then(setD).catch(() => setD({})); }, []);
  if (!d) return <aside className="datasets"><p className="muted">Loading dataset…</p></aside>;

  const hit = (s) => !q || String(s).toLowerCase().includes(q.toLowerCase());

  return (
    <aside className="datasets">
      <h3>Golden dataset</h3>
      <p className="muted small">What the evals are scored against.</p>

      <div className="ds-tabs">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
            {t.title}
          </button>
        ))}
      </div>
      <p className="muted small ds-blurb">
        {TABS.find((t) => t.key === tab)?.tier} — {TABS.find((t) => t.key === tab)?.blurb}
      </p>
      {tab !== "rules" && (
        <input className="ds-search" value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="filter…" aria-label="Filter dataset" />
      )}

      {/* ---------------------------------------------------------- Set A */}
      {tab === "a" && d.a && (() => {
        const rows = d.a.simple.filter((r) => hit(r.message));
        const keep = rows.filter((r) => r.decision === "STORE").length;
        return (
          <>
            <p className="ds-count">
              <b>{keep}</b> to keep · <b>{rows.length - keep}</b> to refuse
              {rows.length !== d.a.simple.length && <> · of {d.a.simple.length}</>}
            </p>
            <ul className="ds-list">
              {rows.map((r, i) => (
                <li key={i} className={r.decision === "STORE" ? "keep" : "drop"}>
                  <span className="ds-msg">{r.message}</span>
                  <span className="ds-meta">
                    {r.decision === "STORE" ? `keep · ${r.type.toLowerCase()}` : "refuse"}
                    {r.topic && <em> · {r.topic}</em>}
                  </span>
                </li>
              ))}
            </ul>
            <h4>Conflict cases</h4>
            <ul className="ds-list">
              {d.a.conflict.filter((c) => hit(c.message)).map((c, i) => (
                <li key={i} className="keep">
                  <span className="ds-msg">{c.message}</span>
                  <span className="ds-meta">
                    already knew “{c.existing.value}” → <b>{c.expected.toLowerCase()}</b>
                    <em> · {c.why}</em>
                  </span>
                </li>
              ))}
            </ul>
          </>
        );
      })()}

      {/* ---------------------------------------------------------- Set B */}
      {tab === "b" && d.b && (() => {
        const seed = Object.fromEntries(d.b.seed.map((m) => [m.id, m]));
        const rows = d.b.queries.filter((r) => hit(r.question));
        return (
          <>
            <p className="ds-count">
              <b>{d.b.seed.length}</b> memories seeded · <b>{rows.length}</b> questions ·
              {" "}<b>{rows.filter((r) => !r.expect.length).length}</b> expect nothing
            </p>
            <ul className="ds-list">
              {rows.map((r, i) => (
                <li key={i} className={r.expect.length ? "keep" : "drop"}>
                  <span className="ds-msg">{r.question}</span>
                  <span className="ds-meta">
                    {r.expect.length
                      ? r.expect.map((id) => seed[id]?.value || id).join(" · ")
                      : "should retrieve nothing"}
                  </span>
                </li>
              ))}
            </ul>
            <h4>The seeded brain</h4>
            <ul className="ds-list">
              {d.b.seed.filter((m) => hit(m.value)).map((m) => (
                <li key={m.id} className="keep">
                  <span className="ds-msg">{m.value}</span>
                  <span className="ds-meta">{m.type.toLowerCase()}{m.topic && <em> · {m.topic}</em>}</span>
                </li>
              ))}
            </ul>
          </>
        );
      })()}

      {/* ---------------------------------------------------------- Set C */}
      {tab === "c" && d.c && (
        <>
          <p className="ds-count">
            <b>{d.c.scripts.length}</b> scripts ·
            {" "}<b>{d.c.scripts.reduce((n, s) => n + s.turns.length, 0)}</b> turns
          </p>
          {d.c.scripts.filter((s) => hit(JSON.stringify(s))).map((s) => (
            <div key={s.id} className="ds-script">
              <h5>{s.id.replace(/_/g, " ")}</h5>
              {s.profile && Object.keys(s.profile).length > 0 && (
                <p className="muted small">{Object.values(s.profile).join(" · ")}</p>
              )}
              <ol className="ds-turns">
                {s.turns.map((t, i) => (
                  <li key={i}>
                    “{t.say}”
                    <span className="ds-meta">
                      {Object.entries(t.assert || {})
                        .map(([k, v]) => EXPECT_WORDS[k]?.[v ? 0 : 1] ?? `${k}=${v}`)
                        .join(" · ") || "no assertion"}
                      {t.judge && <em> · answer judged</em>}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </>
      )}

      {tab === "rules" && <pre className="ds-rules">{d.rules}</pre>}
    </aside>
  );
}
