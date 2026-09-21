import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Datasets from "@/modules/evals/Datasets";

const data = {
  rules: "# Labelling rules\nStore it if it will still be true in 30 days.",
  a: {
    simple: [
      { message: "I am planning to switch jobs next year", decision: "STORE", type: "GOAL", topic: "career" },
      { message: "I had tea at 4pm", decision: "DISCARD", type: "EVENT", topic: "" },
      { message: "Tell me about my career", decision: "DISCARD", type: "EVENT", topic: "" },
    ],
    conflict: [{ message: "Actually I am moving to Bangalore", existing: { value: "living in Delhi" },
                 expected: "SUPERSEDE", why: "city is single-valued" }],
  },
  b: {
    seed: [{ id: "m_goal_switch", value: "switch jobs next year", type: "GOAL", topic: "career" }],
    queries: [
      { question: "What should I focus on for my career?", expect: ["m_goal_switch"] },
      { question: "What is my lucky number?", expect: [] },
    ],
  },
  c: {
    scripts: [{ id: "intro_and_goal", profile: { name: "Rahul" },
                turns: [{ say: "I am planning to switch jobs", assert: { stored: true } },
                        { say: "Why do you say that?", assert: { followup: true }, judge: true }] }],
  },
};

beforeEach(() => {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => data }));
});

test("shows how many messages should be kept versus refused", async () => {
  render(<Datasets />);
  expect(await screen.findByText("1")).toBeInTheDocument();          // 1 to keep
  expect(screen.getByText("I had tea at 4pm")).toBeInTheDocument();
  expect(screen.getByText(/city is single-valued/)).toBeInTheDocument();
});

test("names the memories a question should surface, not their ids", async () => {
  render(<Datasets />);
  fireEvent.click(await screen.findByText("Questions"));
  await waitFor(() => expect(screen.getByText("What should I focus on for my career?")).toBeInTheDocument());
  expect(screen.getAllByText("switch jobs next year").length).toBeGreaterThan(0);
  expect(screen.queryByText("m_goal_switch")).not.toBeInTheDocument();
  expect(screen.getByText("should retrieve nothing")).toBeInTheDocument();
});

test("spells out what each conversation turn should do", async () => {
  render(<Datasets />);
  fireEvent.click(await screen.findByText("Conversations"));
  await waitFor(() => expect(screen.getByText(/intro and goal/)).toBeInTheDocument());
  expect(screen.getByText(/stores a memory/)).toBeInTheDocument();
  expect(screen.getByText(/is a follow-up/)).toBeInTheDocument();
});

test("filters the list as you type", async () => {
  render(<Datasets />);
  await screen.findByText("I had tea at 4pm");
  fireEvent.change(screen.getByLabelText("Filter dataset"), { target: { value: "tea" } });
  expect(screen.getByText("I had tea at 4pm")).toBeInTheDocument();
  expect(screen.queryByText("I am planning to switch jobs next year")).not.toBeInTheDocument();
});

test("shows the labelling rules", async () => {
  render(<Datasets />);
  fireEvent.click(await screen.findByText("Rules"));
  await waitFor(() => expect(screen.getByText(/still be true in 30 days/)).toBeInTheDocument());
});
