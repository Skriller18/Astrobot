"use client";
import { useEffect, useState } from "react";
import { api } from "@/modules/api/client";

export default function Settings({ settings, onChange, onClose }) {
  const [providers, setProviders] = useState({});
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.providers().then(setProviders).catch(() => setProviders({}));
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const models = providers[settings.provider]?.models || [];

  return (
    <div className="panel">
      <div className="row spread">
        <h3>Settings</h3>
        <button className="ghost" onClick={onClose}>close</button>
      </div>

      <label>
        Provider
        <select value={settings.provider || ""}
          onChange={(e) => onChange({ provider: e.target.value, model: undefined })}>
          <option value="">auto (fallback chain)</option>
          {Object.entries(providers).map(([name, p]) => (
            <option key={name} value={name} disabled={!p.available}>
              {name}{p.available ? "" : " — no key"}
            </option>
          ))}
        </select>
      </label>

      <label>
        Model
        <select value={settings.model || ""} onChange={(e) => onChange({ ...settings, model: e.target.value })}
          disabled={!models.length}>
          <option value="">default</option>
          {models.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>

      {health && (
        <p className="muted">
          brain: <b>{health.brain}</b>{health.brain_healthy ? "" : " (down)"} ·
          sessions: <b>{health.sessions}</b>{health.sessions_healthy ? "" : " (down)"}
        </p>
      )}
    </div>
  );
}
