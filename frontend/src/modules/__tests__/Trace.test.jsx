import { render, screen } from "@testing-library/react";
import Trace from "@/modules/chat/Trace";

const trace = (steps) => ({ steps });

const retrieveStep = {
  step: "retrieve", floor: 0.25, top_k: 6,
  candidates: [
    { id: "a", value: "switch jobs next year", score: 0.81, relevance: 1, confidence: 0.9,
      importance: 0.9, decay: 1, included: true },
    { id: "b", value: "likes trekking", score: 0.11, relevance: 0.3, confidence: 0.6,
      importance: 0.6, decay: 1, included: false },
  ],
};

test("renders nothing without a trace", () => {
  const { container } = render(<Trace trace={null} />);
  expect(container).toBeEmptyDOMElement();
});

test("shows detected topics and the follow-up verdict", () => {
  render(<Trace trace={trace([{ step: "understand", topics: ["career"], is_followup: false, followup_score: 0.1 }])} />);
  expect(screen.getByText("career")).toBeInTheDocument();
  expect(screen.getByText("false")).toBeInTheDocument();
});

test("separates memories that were used from those below the floor", () => {
  render(<Trace trace={trace([retrieveStep])} />);
  expect(screen.getByText(/0\.810/)).toBeInTheDocument();
  expect(screen.getByText(/below floor 0\.25/)).toBeInTheDocument();
});

test("explains why retrieval was skipped for a follow-up", () => {
  render(<Trace trace={trace([{ step: "retrieve", skipped: true, reason: "follow-up question" }])} />);
  expect(screen.getByText(/Skipped — follow-up question/)).toBeInTheDocument();
});

test("surfaces a degraded LLM call", () => {
  render(<Trace trace={trace([{ step: "llm", provider: null, degraded: true, fallbacks_tried: ["mock:boom"] }])} />);
  expect(screen.getByText(/Degraded/)).toBeInTheDocument();
});

test("shows the promotion decision with its component scores", () => {
  render(<Trace trace={trace([{
    step: "update_memory", threshold: 0.6,
    decisions: [{ value: "tea at 4pm", action: "DISCARD", reason: "score 0.46 < 0.6", score: 0.456,
      parts: { durability: 0.333, specificity: 1, utility: 0.2, extraction: 0.92 } }],
  }])} />);
  expect(screen.getByText("DISCARD")).toBeInTheDocument();
  expect(screen.getByText(/score 0\.46 < 0\.6/)).toBeInTheDocument();
  expect(screen.getByText("durability")).toBeInTheDocument();
});
