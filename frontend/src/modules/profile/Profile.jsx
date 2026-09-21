"use client";
import { useEffect, useState } from "react";
import { api } from "@/modules/api/client";
import Graph from "@/modules/graph/Graph";

const FIELDS = [
  ["name", "Name"], ["dob", "Date of birth (YYYY-MM-DD)"], ["tob", "Time of birth"],
  ["birth_place", "Birth place"], ["language", "Preferred language"],
];

export default function Profile({ userId, refreshKey, onSaved }) {
  const [form, setForm] = useState({});
  const [graph, setGraph] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!userId) return;
    api.user(userId).then(setForm).catch(() => setForm({}));
    api.brain(userId).then(setGraph).catch(() => setGraph(null));
  }, [userId, refreshKey]);

  async function save(e) {
    e.preventDefault();
    await api.saveUser({ user_id: userId, ...form });
    setSaved(true); setTimeout(() => setSaved(false), 1500);
    onSaved?.();
  }

  async function forget() {
    await api.forget(userId);
    setGraph(await api.brain(userId));
    onSaved?.();
  }

  return (
    <div className="profile">
      <section className="card">
        <h3>Profile</h3>
        <form onSubmit={save}>
          {FIELDS.map(([key, label]) => (
            <label key={key}>
              {label}
              <input value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            </label>
          ))}
          <div className="row">
            <button type="submit">Save</button>
            {saved && <span className="muted">saved</span>}
          </div>
        </form>
        {form.zodiac && (
          <p className="derived">Derived: <b>{form.zodiac}</b> · {form.element} sign</p>
        )}
      </section>

      <section className="card">
        <div className="row spread">
          <h3>Shared Brain</h3>
          <button className="ghost" onClick={forget}>Forget everything</button>
        </div>
        <Graph data={graph} />
        <p className="muted legend">
          <b>●</b> user &nbsp; <b>●</b> memory (fill = confidence) &nbsp; <b>●</b> topic
          &nbsp;·&nbsp; dashed red = superseded
        </p>
      </section>
    </div>
  );
}
