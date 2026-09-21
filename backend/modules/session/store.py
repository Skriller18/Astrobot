"""Episodic memory: every turn, verbatim, forever. MongoDB with a dict fallback."""
from collections import defaultdict

import constants as C
import utils as u


class MemorySessions:
    kind = "memory"

    def __init__(self):
        self.turns = defaultdict(list)

    def healthy(self):
        return True

    def add_turn(self, session_id, user_id, role, content):
        t = {"session_id": session_id, "user_id": user_id, "role": role,
             "content": content, "seq": len(self.turns[session_id]), "ts": u.now(),
             "embedding": u.embed(content) if role == "user" else None}
        self.turns[session_id].append(t)
        return t

    def last_turns(self, session_id, n=C.WINDOW_TURNS):
        return self.turns[session_id][-n:]

    def sessions_for(self, user_id):
        out = [{"session_id": sid, "turns": len(ts), "last_active": ts[-1]["ts"]}
               for sid, ts in self.turns.items() if ts and ts[0]["user_id"] == user_id]
        return sorted(out, key=lambda s: s["last_active"], reverse=True)


class MongoSessions(MemorySessions):
    kind = "mongo"

    def __init__(self, uri=None):
        super().__init__()
        from pymongo import MongoClient
        self.client = MongoClient(uri or C.MONGO_URI,
                                  serverSelectionTimeoutMS=1500)
        self.client.admin.command("ping")
        self.col = self.client.astrobot.turns
        self.col.create_index([("session_id", 1), ("seq", 1)])
        self.col.create_index([("user_id", 1), ("ts", -1)])

    def healthy(self):
        try:
            self.client.admin.command("ping")
            return True
        except Exception:                        # noqa: BLE001
            return False

    def add_turn(self, session_id, user_id, role, content):
        t = {"session_id": session_id, "user_id": user_id, "role": role,
             "content": content, "seq": self.col.count_documents({"session_id": session_id}),
             "ts": u.now(), "embedding": u.embed(content) if role == "user" else None}
        self.col.insert_one(dict(t))
        return t

    def last_turns(self, session_id, n=C.WINDOW_TURNS):
        rows = self.col.find({"session_id": session_id}, {"_id": 0}).sort("seq", -1).limit(n)
        return list(rows)[::-1]

    def sessions_for(self, user_id):
        return list(self.col.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$session_id", "turns": {"$sum": 1},
                        "last_active": {"$max": "$ts"}}},
            {"$project": {"_id": 0, "session_id": "$_id", "turns": 1, "last_active": 1}},
            {"$sort": {"last_active": -1}}]))


def build_sessions():
    if C.SESSIONS == "memory":
        return MemorySessions()
    try:
        return MongoSessions()
    except Exception as e:                       # noqa: BLE001
        print(f"[sessions] mongo unavailable ({e}); using in-process store")
        return MemorySessions()
