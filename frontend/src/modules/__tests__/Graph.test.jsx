import { render, screen } from "@testing-library/react";
import Graph from "@/modules/graph/Graph";

const data = {
  nodes: [
    { id: "u", label: "Rahul", kind: "user" },
    { id: "m1", label: "switch jobs", kind: "memory", type: "GOAL", confidence: 0.9, status: "active" },
    { id: "m2", label: "living in Delhi", kind: "memory", type: "ATTRIBUTE", confidence: 0.8, status: "superseded" },
    { id: "topic:career", label: "career", kind: "topic" },
  ],
  edges: [
    { source: "u", target: "m1", label: "HAS_GOAL" },
    { source: "m1", target: "topic:career", label: "ABOUT" },
  ],
};

test("prompts the user when the graph is empty", () => {
  render(<Graph data={{ nodes: [], edges: [] }} />);
  expect(screen.getByText(/No graph yet/)).toBeInTheDocument();
});

test("labels every relationship, including on a busy graph", () => {
  render(<Graph data={data} />);
  expect(screen.getByText("Rahul")).toBeInTheDocument();
  expect(screen.getByText("career")).toBeInTheDocument();
  expect(screen.getByText("HAS_GOAL")).toBeInTheDocument();
  expect(screen.getByText("ABOUT")).toBeInTheDocument();
});

test("fades a superseded memory instead of hiding it", () => {
  const { container } = render(<Graph data={data} />);
  const faded = [...container.querySelectorAll("g[opacity]")].filter((g) => g.getAttribute("opacity") !== "1");
  expect(faded).toHaveLength(1);
});

test("spreads a ring horizontally instead of collapsing onto one line", () => {
  const two = {
    nodes: [
      { id: "u", label: "U", kind: "user" },
      { id: "a", label: "A", kind: "memory", type: "GOAL", confidence: 1, status: "active" },
      { id: "b", label: "B", kind: "memory", type: "GOAL", confidence: 1, status: "active" },
    ],
    edges: [],
  };
  const { container } = render(<Graph data={two} />);
  const xs = [...container.querySelectorAll("circle")].map((c) => c.getAttribute("cx"));
  expect(new Set(xs).size).toBeGreaterThan(1);
});

const busyGraph = (n) => ({
  nodes: Array.from({ length: n }, (_, i) => ({
    id: `m${i}`, label: `memory ${i}`, kind: "memory", type: "GOAL",
    confidence: 0.9, status: "active",
  })).concat([{ id: "u", label: "U", kind: "user" }]),
  edges: Array.from({ length: n }, (_, i) => ({ source: "u", target: `m${i}`, label: "HAS_GOAL" })),
});

test("keeps labelling relationships however busy the graph gets", () => {
  expect(render(<Graph data={busyGraph(12)} />).container
    .querySelectorAll(".edge-label").length).toBe(12);
  expect(render(<Graph data={busyGraph(30)} />).container
    .querySelectorAll(".edge-label").length).toBe(30);
});

test("draws the repetitive ABOUT edges faintly so typed ones stand out", () => {
  const { container } = render(<Graph data={data} />);
  expect(container.querySelectorAll(".edge-faint").length).toBe(1);
});

test("wraps a long memory label instead of letting it run over", () => {
  const long = {
    nodes: [{ id: "m", kind: "memory", type: "GOAL", confidence: 1, status: "active",
              label: "move into product management by early 2027" }],
    edges: [],
  };
  const { container } = render(<Graph data={long} />);
  expect(container.querySelectorAll(".node-label tspan").length).toBe(2);
});
