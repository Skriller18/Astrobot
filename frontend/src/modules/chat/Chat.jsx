"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/modules/api/client";

export default function Chat({ userId, sessionId, settings, onTrace, onChanged }) {
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState("");
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;
    api.turns(sessionId).then(setTurns).catch(() => setTurns([]));
  }, [sessionId]);

  // Block body, not a concise one: recent Chrome returns a Promise from a smooth
  // scrollIntoView, and React would treat that return value as a cleanup function.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy, streaming]);

  async function send(e) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || busy) return;
    setDraft(""); setError(null); setBusy(true); setStreaming("");
    setTurns((t) => [...t, { role: "user", content: message }]);

    // Accumulate outside state: React batches updates, so a token arriving during
    // a pending render would otherwise be dropped.
    let text = "";
    try {
      await api.chatStream(
        { user_id: userId, session_id: sessionId, message, ...settings },
        {
          // Retrieval scoring is known before the first token, so show it immediately.
          context: (ctx) => onTrace({ trace: ctx }),
          token: (t) => { text += t; setStreaming(text); },
          done: (res) => {
            setTurns((prev) => [...prev, { role: "assistant", content: res.response }]);
            setStreaming("");
            onTrace(res);
            onChanged?.();
          },
          error: (e2) => setError(e2.detail),
        }
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setStreaming("");
    }
  }

  return (
    <div className="chat">
      <div className="turns">
        {turns.length === 0 && (
          <p className="muted empty">Say something about yourself, then ask a question.</p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`turn ${t.role}`}>{t.content}</div>
        ))}
        {streaming && <div className="turn assistant streaming">{streaming}</div>}
        {busy && !streaming && <div className="turn assistant muted">thinking…</div>}
        {error && <div className="turn error">{error}</div>}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about your chart, your career, anything…" aria-label="Message" />
        <button disabled={busy || !draft.trim()}>Send</button>
      </form>
    </div>
  );
}
