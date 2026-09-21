"use client";
import { useEffect, useState } from "react";
import Sidebar from "@/modules/Sidebar";
import Chat from "@/modules/chat/Chat";
import Trace from "@/modules/chat/Trace";
import Profile from "@/modules/profile/Profile";
import Settings from "@/modules/settings/Settings";
import Evals from "@/modules/evals/Evals";

const newSessionId = () => `s-${Date.now().toString(36)}`;

export default function Home() {
  const [userId, setUserId] = useState("rahul");
  // Session ids use Date.now(), so they must be generated on the client only --
  // creating one during render makes the server and client disagree and React
  // throws away the server-rendered DOM.
  const [sessionId, setSessionId] = useState(null);
  useEffect(() => {
    setSessionId(newSessionId());
  }, []);
  const [tab, setTab] = useState("chat");
  const [showTrace, setShowTrace] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState({});
  const [last, setLast] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = () => setRefreshKey((k) => k + 1);
  const pick = (uid, sid) => { setUserId(uid); setSessionId(sid || newSessionId()); };

  return (
    <main className="layout">
      <Sidebar userId={userId} sessionId={sessionId} refreshKey={refreshKey}
        onPick={pick} onNewSession={() => setSessionId(newSessionId())} />

      <section className="main">
        <header>
          <div className="tabs">
            {[["chat", "Chat"], ["profile", "Profile & Brain"], ["evals", "Evals"]].map(([t, label]) => (
              <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                {label}
              </button>
            ))}
          </div>
          <div className="row">
            <label className="toggle">
              <input type="checkbox" checked={showTrace}
                onChange={(e) => setShowTrace(e.target.checked)} />
              Show underneath process
            </label>
            <button className="ghost" onClick={() => setShowSettings((s) => !s)}>Settings</button>
          </div>
        </header>

        {showSettings && (
          <Settings settings={settings}
            onChange={(s) => setSettings((p) => ({ ...p, ...s }))}
            onClose={() => setShowSettings(false)} />
        )}

        <div className="workspace">
          {tab === "chat" && (
            <Chat userId={userId} sessionId={sessionId} settings={settings}
              onTrace={setLast} onChanged={refresh} key={sessionId} />
          )}
          {tab === "profile" && <Profile userId={userId} refreshKey={refreshKey} onSaved={refresh} />}
          {tab === "evals" && <Evals />}
          {tab === "chat" && showTrace && <Trace trace={last?.trace} />}
        </div>
      </section>
    </main>
  );
}
