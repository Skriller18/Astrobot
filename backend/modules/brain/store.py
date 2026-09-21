"""Shared Brain: the per-user knowledge graph.

Neo4j when reachable, an in-process graph when not, behind one interface so the
chat flow never learns which it got.
"""
import uuid
from datetime import datetime

import constants as C
import utils as u

SCHEMA = [
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (n:User) REQUIRE n.user_id IS UNIQUE",
    "CREATE CONSTRAINT mem_id IF NOT EXISTS FOR (n:Memory) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (n:Topic) REQUIRE n.name IS UNIQUE",
    "CREATE INDEX mem_status IF NOT EXISTS FOR (n:Memory) ON (n.status)",
]
REL = {"GOAL": "HAS_GOAL", "PREFERENCE": "PREFERS", "INTEREST": "INTERESTED_IN",
       "ATTRIBUTE": "HAS_ATTRIBUTE", "EVENT": "REMEMBERS", "IDENTITY": "HAS_IDENTITY"}

PROFILE_FIELDS = ("name", "dob", "tob", "birth_place", "language")


def _new_memory(user_id, mtype, value, topic, confidence, source, session_id):
    return {"id": uuid.uuid4().hex, "user_id": user_id, "type": mtype, "value": value,
            "topic": topic, "confidence": confidence, "source_message": source,
            "session_id": session_id, "status": "active", "embedding": u.embed(value),
            "created_at": u.now(), "last_affirmed": u.now()}


class MemoryBrain:
    """In-process fallback. Same methods as the Neo4j store."""
    kind = "memory"

    def __init__(self):
        self.users, self.memories = {}, {}

    def healthy(self):
        return True

    def upsert_user(self, user_id, **profile):
        user = self.users.setdefault(user_id, {"user_id": user_id, "created_at": u.now()})
        user.update({k: v for k, v in profile.items() if v is not None})
        if user.get("dob"):
            user["zodiac"] = u.sun_sign(user["dob"])
            user["element"] = u.element(user["zodiac"])
        return user

    def get_user(self, user_id):
        return self.users.get(user_id)

    def list_users(self):
        return list(self.users.values())

    def add_memory(self, user_id, mtype, value, topic, confidence, source, session_id):
        m = _new_memory(user_id, mtype, value, topic, confidence, source, session_id)
        self.memories[m["id"]] = m
        return m

    def active_memories(self, user_id):
        return [m for m in self.memories.values()
                if m["user_id"] == user_id and m["status"] == "active"]

    def update_memory(self, mem_id, **fields):
        self.memories[mem_id].update(fields)

    def supersede(self, old_id, new_id):
        self.memories[old_id].update(status="superseded", superseded_by=new_id)

    def clear_memories(self, user_id):
        for k in [k for k, m in self.memories.items() if m["user_id"] == user_id]:
            del self.memories[k]

    def graph(self, user_id):
        """Nodes and edges for the frontend visualiser."""
        user = self.get_user(user_id)
        if not user:
            return {"nodes": [], "edges": []}
        nodes = [{"id": user_id, "label": user.get("name") or user_id, "kind": "user"}]
        edges, topics = [], set()
        for m in self.memories.values():
            if m["user_id"] != user_id:
                continue
            nodes.append({"id": m["id"], "label": m["value"], "kind": "memory",
                          "type": m["type"], "confidence": round(m["confidence"], 2),
                          "status": m["status"],
                          "decay": round(u.decay(m["type"], m["last_affirmed"]), 2)})
            edges.append({"source": user_id, "target": m["id"], "label": REL.get(m["type"], "KNOWS")})
            if m.get("topic"):
                topics.add(m["topic"])
                edges.append({"source": m["id"], "target": f"topic:{m['topic']}", "label": "ABOUT"})
            if m.get("superseded_by"):
                edges.append({"source": m["superseded_by"], "target": m["id"], "label": "SUPERSEDES"})
        nodes += [{"id": f"topic:{t}", "label": t, "kind": "topic"} for t in topics]
        return {"nodes": nodes, "edges": edges}


class Neo4jBrain(MemoryBrain):
    """Same API in Cypher. Falls back to the parent's dicts if the driver is down."""
    kind = "neo4j"

    def __init__(self, uri=None, user=None, password=None):
        super().__init__()
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(
            uri or C.NEO4J_URI,
            auth=(user or C.NEO4J_USER, password or C.NEO4J_PASSWORD),
            # an empty graph has no SUPERSEDES yet; that is expected, not a problem
            warn_notification_severity="OFF")
        self.driver.verify_connectivity()
        with self.driver.session() as s:
            for q in SCHEMA:
                s.run(q)

    def healthy(self):
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:                        # noqa: BLE001
            return False

    def _run(self, q, **p):
        with self.driver.session() as s:
            return [r.data() for r in s.run(q, **p)]

    def upsert_user(self, user_id, **profile):
        p = {k: v for k, v in profile.items() if v is not None}
        if p.get("dob"):
            p["zodiac"], p["element"] = u.sun_sign(p["dob"]), u.element(u.sun_sign(p["dob"]))
        self._run("MERGE (n:User {user_id:$uid}) SET n += $p, "
                  "n.created_at = coalesce(n.created_at, datetime())", uid=user_id, p=p)
        return self.get_user(user_id)

    def get_user(self, user_id):
        r = self._run("MATCH (n:User {user_id:$uid}) RETURN n", uid=user_id)
        return _plain(r[0]["n"]) if r else None

    def list_users(self):
        return [_plain(r["n"]) for r in self._run("MATCH (n:User) RETURN n ORDER BY n.user_id")]

    def add_memory(self, user_id, mtype, value, topic, confidence, source, session_id):
        m = _new_memory(user_id, mtype, value, topic, confidence, source, session_id)
        self._run(
            f"MATCH (usr:User {{user_id:$uid}}) "
            f"CREATE (m:Memory {{id:$id, type:$type, value:$value, topic:$topic, "
            f"confidence:$confidence, source_message:$source, session_id:$sid, "
            f"status:'active', embedding:$emb, created_at:datetime(), last_affirmed:datetime()}}) "
            f"CREATE (usr)-[:{REL.get(mtype,'KNOWS')}]->(m) "
            f"WITH m WHERE $topic <> '' "
            f"MERGE (t:Topic {{name:$topic}}) MERGE (m)-[:ABOUT]->(t)",
            uid=user_id, id=m["id"], type=mtype, value=value, topic=topic or "",
            confidence=confidence, source=source, sid=session_id, emb=m["embedding"])
        return m

    def active_memories(self, user_id):
        rows = self._run("MATCH (:User {user_id:$uid})-->(m:Memory {status:'active'}) "
                         "RETURN m", uid=user_id)
        out = []
        for r in rows:
            m = dict(r["m"])
            m["last_affirmed"] = _dt(m.get("last_affirmed"))
            m["user_id"] = user_id
            out.append(m)
        return out

    def update_memory(self, mem_id, **fields):
        if "last_affirmed" in fields:
            fields.pop("last_affirmed")
            self._run("MATCH (m:Memory {id:$id}) SET m.last_affirmed = datetime()", id=mem_id)
        if fields:
            self._run("MATCH (m:Memory {id:$id}) SET m += $f", id=mem_id, f=fields)

    def supersede(self, old_id, new_id):
        self._run("MATCH (o:Memory {id:$o}), (n:Memory {id:$n}) "
                  "SET o.status='superseded' MERGE (n)-[:SUPERSEDES]->(o)", o=old_id, n=new_id)

    def clear_memories(self, user_id):
        self._run("MATCH (:User {user_id:$uid})-->(m:Memory) DETACH DELETE m", uid=user_id)

    def graph(self, user_id):
        rows = self._run(
            "MATCH (usr:User {user_id:$uid}) OPTIONAL MATCH (usr)-[r]->(m:Memory) "
            "OPTIONAL MATCH (m)-[:ABOUT]->(t:Topic) "
            "OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory) "
            "RETURN usr, r, m, t, old", uid=user_id)
        if not rows:
            return {"nodes": [], "edges": []}
        usr = rows[0]["usr"]
        nodes = {user_id: {"id": user_id, "label": usr.get("name") or user_id, "kind": "user"}}
        edges = []
        for r in rows:
            m, t, old = r["m"], r["t"], r["old"]
            if not m:
                continue
            nodes[m["id"]] = {"id": m["id"], "label": m["value"], "kind": "memory",
                              "type": m["type"], "confidence": round(m["confidence"], 2),
                              "status": m["status"],
                              "decay": round(u.decay(m["type"], _dt(m["last_affirmed"])), 2)}
            edges.append({"source": user_id, "target": m["id"], "label": r["r"][1]})
            if t:
                nodes[f"topic:{t['name']}"] = {"id": f"topic:{t['name']}",
                                               "label": t["name"], "kind": "topic"}
                edges.append({"source": m["id"], "target": f"topic:{t['name']}", "label": "ABOUT"})
            if old:
                edges.append({"source": m["id"], "target": old["id"], "label": "SUPERSEDES"})
        return {"nodes": list(nodes.values()), "edges": edges}


def _dt(v):
    return v.to_native() if hasattr(v, "to_native") else (v or datetime.utcnow())


def _plain(node):
    """Neo4j temporals serialise as internal objects; hand the API ISO strings."""
    return {k: (_dt(v).isoformat() if hasattr(v, "to_native") else v)
            for k, v in dict(node).items() if k != "embedding"}


def build_brain():
    """Neo4j if we can reach it, in-process otherwise. Never raises."""
    if C.BRAIN == "memory":
        return MemoryBrain()
    try:
        return Neo4jBrain()
    except Exception as e:                       # noqa: BLE001
        print(f"[brain] neo4j unavailable ({e}); using in-process graph")
        return MemoryBrain()
