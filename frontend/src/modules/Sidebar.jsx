"use client";
import { useEffect, useState } from "react";
import { api } from "@/modules/api/client";

export default function Sidebar({ userId, sessionId, onPick, onNewSession, refreshKey }) {
  const [users, setUsers] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [draft, setDraft] = useState("");

  useEffect(() => { api.users().then(setUsers).catch(() => setUsers([])); }, [refreshKey]);
  useEffect(() => {
    if (userId) api.sessions(userId).then(setSessions).catch(() => setSessions([]));
  }, [userId, refreshKey]);

  async function addUser(e) {
    e.preventDefault();
    const id = draft.trim();
    if (!id) return;
    await api.saveUser({ user_id: id, name: id });
    setDraft(""); onPick(id);
  }

  return (
    <nav className="sidebar">
      <h1>MyNaksh</h1>

      <h2>Profiles</h2>
      <ul>
        {users.map((u) => (
          <li key={u.user_id}>
            <button className={u.user_id === userId ? "active" : ""} onClick={() => onPick(u.user_id)}>
              {u.name || u.user_id}
              {u.zodiac && <span className="tag">{u.zodiac}</span>}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={addUser} className="new-user">
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="new profile id" />
        <button>+</button>
      </form>

      <h2>Sessions</h2>
      <ul>
        {sessions.map((s) => (
          <li key={s.session_id}>
            <button className={s.session_id === sessionId ? "active" : ""}
              onClick={() => onPick(userId, s.session_id)}>
              {s.session_id}<span className="tag">{s.turns}</span>
            </button>
          </li>
        ))}
      </ul>
      <button className="ghost wide" onClick={onNewSession}>+ New session</button>
    </nav>
  );
}
