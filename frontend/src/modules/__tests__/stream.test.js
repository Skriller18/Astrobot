import { api } from "@/modules/api/client";

/** Builds a fetch Response whose body streams the given SSE frames. */
function sseResponse(frames, { chunkSize = 7 } = {}) {
  const payload = frames.join("");
  const bytes = new TextEncoder().encode(payload);
  let i = 0;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (i >= bytes.length) return { done: true, value: undefined };
          const slice = bytes.slice(i, i + chunkSize);
          i += chunkSize;
          return { done: false, value: slice };
        },
      }),
    },
  };
}

const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

beforeEach(() => { global.fetch = jest.fn(); });

test("dispatches context, tokens and done in order", async () => {
  global.fetch.mockResolvedValue(sseResponse([
    frame("context", { steps: [{ step: "understand", topics: ["career"] }] }),
    frame("token", "Based "), frame("token", "on "), frame("token", "your goal"),
    frame("done", { response: "Based on your goal", context_used: ["switch jobs"] }),
  ]));

  const seen = [];
  const tokens = [];
  await api.chatStream({ user_id: "u", session_id: "s", message: "hi" }, {
    context: (c) => seen.push(["context", c.steps[0].topics[0]]),
    token: (t) => { tokens.push(t); seen.push(["token"]); },
    done: (d) => seen.push(["done", d.response]),
  });

  expect(seen[0]).toEqual(["context", "career"]);
  expect(tokens.join("")).toBe("Based on your goal");
  expect(seen[seen.length - 1]).toEqual(["done", "Based on your goal"]);
});

test("reassembles frames split across network chunks", async () => {
  // One byte at a time: every frame boundary lands mid-frame.
  global.fetch.mockResolvedValue(sseResponse(
    [frame("token", "alpha"), frame("token", "beta"), frame("done", { response: "alphabeta" })],
    { chunkSize: 1 }
  ));
  const tokens = [];
  await api.chatStream({}, { token: (t) => tokens.push(t) });
  expect(tokens).toEqual(["alpha", "beta"]);
});

test("ignores events with no registered handler", async () => {
  global.fetch.mockResolvedValue(sseResponse([frame("surprise", { x: 1 }), frame("token", "ok")]));
  const tokens = [];
  await expect(api.chatStream({}, { token: (t) => tokens.push(t) })).resolves.toBeUndefined();
  expect(tokens).toEqual(["ok"]);
});

test("surfaces a non-200 before streaming starts", async () => {
  global.fetch.mockResolvedValue({
    ok: false, statusText: "Bad Request", json: async () => ({ detail: "unknown provider 'nope'" }),
  });
  await expect(api.chatStream({}, {})).rejects.toThrow("unknown provider 'nope'");
});
