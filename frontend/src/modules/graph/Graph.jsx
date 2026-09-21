"use client";
import { useMemo } from "react";

/** Radial layout: user at the centre, memories in a ring, topics outside them.
 *  ponytail: hand-rolled SVG beats pulling in a graph library for three node kinds. */
const FILL = { user: "#4f46e5", memory: "#0ea5e9", topic: "#64748b" };
const R = { user: 22, memory: 16, topic: 18 };

/** Rings grow with how many nodes they hold, so a busy brain does not pile up.
 *  The multiplier is per-node arc length: a wrapped label is ~110px wide, and the
 *  labels nearest the top and bottom of the ring are horizontal, so they need the
 *  most room. Measured at 14 nodes: 26 leaves 2 collisions, 38 leaves none. */
const radius = (kind, n) => ({
  user: 0,
  memory: Math.max(155, 38 * n),
  topic: Math.max(290, 38 * n + 140),
}[kind]);

/** Break a label onto at most two lines at a word boundary. */
function wrap(text, max = 16) {
  const s = String(text);
  if (s.length <= max) return [s];
  const cut = s.lastIndexOf(" ", max);
  const head = cut > 6 ? s.slice(0, cut) : s.slice(0, max);
  const tail = s.slice(head.length).trim();
  return [head, tail.length > max ? tail.slice(0, max - 1) + "…" : tail];
}

function layout(nodes) {
  const byKind = { user: [], memory: [], topic: [] };
  nodes.forEach((n) => byKind[n.kind]?.push(n));

  const size = 2 * (radius("topic", byKind.topic.length) + 90);
  const c = size / 2;
  const placed = {};

  Object.entries(byKind).forEach(([kind, list]) =>
    list.forEach((n, i) => {
      // Half-step offset: without it two nodes land at -90 and +90 degrees, where
      // cos is 0 for both, and the whole ring collapses onto one vertical line.
      const angle = (2 * Math.PI * (i + 0.5)) / Math.max(list.length, 1) - Math.PI / 2;
      const r = radius(kind, list.length);
      const x = c + r * Math.cos(angle);
      const y = c + r * Math.sin(angle);
      // Labels sit further out along the same spoke and are anchored by which side
      // of the circle they are on, so neighbouring labels grow apart, not over.
      const out = R[kind] + 8;
      placed[n.id] = {
        ...n, x, y, angle,
        lx: x + out * Math.cos(angle) * 1.05,
        ly: y + out * Math.sin(angle) + (Math.sin(angle) > 0 ? 8 : -2),
        anchor: Math.cos(angle) > 0.25 ? "start" : Math.cos(angle) < -0.25 ? "end" : "middle",
        lines: wrap(n.label),
      };
    })
  );
  return { placed, size, c };
}

export default function Graph({ data }) {
  const { placed, size, c } = useMemo(() => layout(data?.nodes || []), [data]);
  if (!data?.nodes?.length)
    return <p className="muted">No graph yet — chat a little and facts will appear here.</p>;

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="graph" role="img"
         aria-label="User knowledge graph">
      {data.edges.map((e, i) => {
        const a = placed[e.source], b = placed[e.target];
        if (!a || !b) return null;
        const sup = e.label === "SUPERSEDES";
        // Always label the edge -- the relationship type IS the schema, and hiding it
        // on busier graphs made exactly the graphs worth reading the least readable.
        // Overlap is handled by placing labels inward and giving them a white halo;
        // the repetitive ABOUT edges are drawn faintly so the typed ones stand out.
        const faint = e.label === "ABOUT";
        return (
          <g key={i}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={sup ? "#f43f5e" : "#e2e8f0"} strokeWidth={sup ? 1.5 : 1}
                  strokeDasharray={sup ? "4 3" : undefined}>

            </line>
            {/* 38% along the line rather than the midpoint: node labels live on the
                rim, so pulling the relationship inward keeps the two off each other. */}
            <text x={a.x + 0.38 * (b.x - a.x)} y={a.y + 0.38 * (b.y - a.y) - 3}
                  className={`edge-label${faint ? " edge-faint" : ""}`}>
              {e.label}
            </text>
          </g>
        );
      })}

      {Object.values(placed).map((n) => (
        <g key={n.id} opacity={n.status === "superseded" ? 0.4 : 1}>
          <circle cx={n.x} cy={n.y} r={R[n.kind]} fill={FILL[n.kind]}
                  fillOpacity={n.kind === "memory" ? 0.2 + 0.7 * (n.confidence ?? 1) : 0.9}
                  stroke={FILL[n.kind]} strokeWidth="1.5" />
          {n.kind === "memory" && (
            <text x={n.x} y={n.y + 4} className="node-badge">{n.type?.[0]}</text>
          )}
          {/* Only memories carry a tooltip -- for the others it would just repeat
              the visible label. */}
          {n.kind === "memory" && (
            <title>{`${n.type} · confidence ${n.confidence} · decay ${n.decay}`}</title>
          )}
          <text x={n.lx} y={n.ly} className={`node-label label-${n.kind}`}
                textAnchor={n.anchor}>
            {n.lines.map((line, i) => (
              <tspan key={i} x={n.lx} dy={i === 0 ? 0 : 11}>{line}</tspan>
            ))}
          </text>
        </g>
      ))}
    </svg>
  );
}
