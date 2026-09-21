import { api } from "@/modules/api/client";

beforeEach(() => { global.fetch = jest.fn(); });

test("posts a chat message and returns the payload", async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ response: "hi" }) });
  await expect(api.chat({ user_id: "u", session_id: "s", message: "hello" }))
    .resolves.toEqual({ response: "hi" });
  const [url, opts] = global.fetch.mock.calls[0];
  expect(url).toMatch(/\/chat$/);
  expect(JSON.parse(opts.body).message).toBe("hello");
});

test("surfaces the server's error detail", async () => {
  global.fetch.mockResolvedValue({
    ok: false, statusText: "Bad Request", json: async () => ({ detail: "unknown provider 'nope'" }),
  });
  await expect(api.chat({})).rejects.toThrow("unknown provider 'nope'");
});

test("falls back to the status text when there is no detail", async () => {
  global.fetch.mockResolvedValue({ ok: false, statusText: "Server Error", json: async () => ({}) });
  await expect(api.health()).rejects.toThrow("Server Error");
});
