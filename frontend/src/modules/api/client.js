const API = "/api";   // proxied to the backend by next.config.js

async function call(path, options) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

/** Reads an SSE stream, invoking `on[event]` for each message as it arrives. */
async function sse(path, body, on) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; keep any partial tail in the buffer.
    const frames = buffer.split("\n\n");
    buffer = frames.pop();
    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1];
      const data = frame.match(/^data: (.+)$/m)?.[1];
      if (event && data) on[event]?.(JSON.parse(data));
    }
  }
}

export const api = {
  chat: (body) => call("/chat", { method: "POST", body: JSON.stringify(body) }),
  chatStream: (body, on) => sse("/chat/stream", body, on),
  users: () => call("/users"),
  user: (id) => call(`/users/${id}`),
  saveUser: (body) => call("/users", { method: "POST", body: JSON.stringify(body) }),
  brain: (id) => call(`/users/${id}/brain`),
  sessions: (id) => call(`/users/${id}/sessions`),
  turns: (id) => call(`/sessions/${id}/turns`),
  forget: (id) => call(`/users/${id}/memory`, { method: "DELETE" }),
  providers: () => call("/providers"),
  evals: (run) => call(`/evals${run ? `?run=${run}` : ""}`),
  evalRuns: () => call("/evals/runs"),
  evalDatasets: () => call("/evals/datasets"),
  health: () => call("/health"),
};
