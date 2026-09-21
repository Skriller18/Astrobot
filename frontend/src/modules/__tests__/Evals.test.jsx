import { render, screen, waitFor } from "@testing-library/react";
import Evals from "@/modules/evals/Evals";

const results = {
  generated_at: "2026-09-21T10:00:00", duration_s: 412,
  tiers: {
    tier1: { metrics: { accuracy_pct: 95.2, junk_stored: 2, facts_missed: 1,
                        conflict_accuracy_pct: 83.3, n: 62 },
             failures: [{ message: "My friend is a Scorpio", expected: "DISCARD",
                          got: "CREATE", score: 0.811 }] },
    tier2: { metrics: { precision_pct: 64.3, recall_pct: 90, exact_match_pct: 56.5,
                        correct_silence: "7/8", avg_injected: 1.83, n: 23 },
             memories: { m_goal_pm: { value: "move into product management", type: "GOAL", topic: "career" },
                         m_int_entre: { value: "entrepreneurship", type: "INTEREST", topic: "career" } },
             rows: [{ question: "Will I get a promotion?", expected: ["m_goal_pm"],
                      got: ["m_goal_pm", "m_int_entre"], extra: ["m_int_entre"], missed: [], ok: false }] },
    tier3_mock: { config: { provider: "mock" }, metrics: { scripts_passed: "7/10", turns_passed: "13/19" }, rows: [] },
    tier3_real: { config: { provider: "gemini" }, metrics: { scripts_passed: "9/10", turns_passed: "18/19" },
                  rows: [{ script: "correction", say: "Where should I settle down?",
                           expected: { retrieved: true }, ok: false }] },
    tier4: {
      judge: "glm-5.3:cloud", candidates: ["gemini-3.8-flash"],
      metrics: {
        advice_on_vs_off: { on: 15, off: 5, tie: 4 },
        personalised_on_vs_off: { on: 19, off: 2, tie: 3 },
        invented_facts_brain_on: 1, invented_facts_brain_off: 0,
        controls_advice: { on: 2, off: 2, tie: 0 },
        per_model: { "gemini-3.8-flash": { advice: { on: 5, off: 1, tie: 0 },
                                           personalised: { on: 6, off: 0, tie: 0 }, invented_on: 0 } },
        model_rank_points: { "gemini-3.8-flash": 22, "deepseek-v4.1-flash:cloud": 18 },
        judged_pairs: 24, control_pairs: 8, judge_errors: 0,
      },
      pairs: [{ question: "What should I focus on?", model: "gemini-3.8-flash",
                is_control: false, advice_winner: "on", personalised_winner: "on",
                reason: "uses the stated career goal" }],
      ranks: [], generations: [{ model: "gemini-3.8-flash", question: "q",
                                 brain_on: "with memory", brain_off: "generic" }],
    },
  },
  sweep: {
    grid: { PROMOTION_THRESHOLD: ["0.5", "0.6"] },
    runs: [
      { constant: "PROMOTION_THRESHOLD", value: 0.5, primary_metric: "accuracy_pct",
        primary: 90.3, counter_metric: "junk_stored", counter: 5, is_current: false },
      { constant: "PROMOTION_THRESHOLD", value: 0.6, primary_metric: "accuracy_pct",
        primary: 95.2, counter_metric: "junk_stored", counter: 2, is_current: true },
    ],
  },
};

beforeEach(() => { global.fetch = jest.fn(); });

// The page loads two endpoints: the run list and the results themselves.
const mock = (data, runList = []) =>
  global.fetch.mockImplementation((url) =>
    Promise.resolve({ ok: true, json: async () =>
      String(url).includes("/evals/runs") ? runList : data }));

test("tells you how to generate results when there are none", async () => {
  global.fetch.mockImplementation(() =>
    Promise.resolve({ ok: false, statusText: "Not Found", json: async () => ({ detail: "no eval results yet" }) }));
  render(<Evals />);
  expect(await screen.findByText(/No eval results yet/)).toBeInTheDocument();
});

test("shows each tier's headline metrics", async () => {
  mock(results);
  render(<Evals />);
  expect(await screen.findByText("95.2%")).toBeInTheDocument();   // tier 1 accuracy
  expect(screen.getByText("64.3%")).toBeInTheDocument();          // tier 2 precision
  expect(screen.getByText("7/8")).toBeInTheDocument();            // correct silence
  expect(screen.getByText("15 vs 5")).toBeInTheDocument();        // tier 4 advice
});

test("renders memories by what they say, not by their id", async () => {
  mock(results);
  render(<Evals />);
  // appears in both the "should have used" and "actually used" columns
  expect((await screen.findAllByText("move into product management")).length).toBe(2);
  expect(screen.getByText("entrepreneurship")).toBeInTheDocument();
  expect(screen.queryByText("m_goal_pm")).not.toBeInTheDocument();
  expect(screen.queryByText("m_int_entre")).not.toBeInTheDocument();
});

test("offers every stored run in the picker", async () => {
  mock(results, ["run-20260921-143811", "run-20260921-123242"]);
  render(<Evals />);
  expect(await screen.findByText("21 Sep 14:38")).toBeInTheDocument();
  expect(screen.getByText("21 Sep 12:32")).toBeInTheDocument();
  expect(screen.getByText("latest")).toBeInTheDocument();
});

test("marks the sweep's winning configuration and the current one", async () => {
  mock(results);
  const { container } = render(<Evals />);
  await waitFor(() => expect(screen.getByText("PROMOTION_THRESHOLD")).toBeInTheDocument());
  expect(container.querySelectorAll(".row-best").length).toBeGreaterThan(0);
  expect(screen.getAllByText("in use").length).toBe(1);
});

test("ranks the models and flags the best one", async () => {
  mock(results);
  render(<Evals />);
  await waitFor(() => expect(screen.getByText("22")).toBeInTheDocument());
  expect(screen.getByText("top ranked")).toBeInTheDocument();
});

test("explains that the mock-vs-real gap is the extractor", async () => {
  mock(results);
  render(<Evals />);
  expect(await screen.findByText(/That gap is the stub extractor/)).toBeInTheDocument();
});
