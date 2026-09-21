"""The promotion gate: decide what reaches the brain, and how it lands there."""
import constants as C
import utils as u


def _score(cand, message):
    mtype, value = cand.get("type", "STATE"), (cand.get("value") or "").strip()
    topic = cand.get("topic") or (u.classify_topics(message) or [""])[0]
    score, parts = u.promotion_score(
        mtype, value, topic, message,
        self_report=float(cand.get("confidence", 0.8)),
        has_qualifier=u.has_qualifier(message),
        slots_complete=bool(mtype and value and topic))
    return mtype, value, topic, score, parts


def evaluate(candidates, message, existing):
    """Score every candidate and pick its action. Pure -- no writes happen here."""
    out = []
    for cand in candidates:
        mtype, value, topic, score, parts = _score(cand, message)
        d = {"type": mtype, "value": value, "topic": topic,
             "score": round(score, 3), "parts": {k: round(v, 3) for k, v in parts.items()}}

        if not u.passes_gates(message, mtype, value):
            out.append({**d, "action": "DISCARD", "reason": "failed hard gates"})
            continue
        if score < C.PROMOTION_THRESHOLD:
            out.append({**d, "action": "DISCARD",
                        "reason": f"score {score:.2f} < {C.PROMOTION_THRESHOLD}"})
            continue

        match, sim = _closest(value, mtype, existing)
        if not match:
            out.append({**d, "action": "CREATE", "reason": "no similar memory"})
            continue
        action = u.match_action(sim, C.TYPES[mtype]["single"],
                                match["value"].strip().lower() != value.lower(),
                                same_slot=match.get("topic") == topic)
        out.append({**d, "action": action, "match_id": match["id"],
                    "similarity": round(sim, 3),
                    "reason": f"closest existing memory at cosine {sim:.2f}"})
    return out


def _closest(value, mtype, existing):
    same = [m for m in existing if m["type"] == mtype]
    if not same:
        return None, 0.0
    emb = u.embed(value)
    best = max(same, key=lambda m: u.cosine(emb, m.get("embedding") or []))
    return best, u.cosine(emb, best.get("embedding") or [])


def apply(decisions, brain, user_id, message, session_id):
    """Carry out the decided actions. Returns what actually changed."""
    applied = []
    for d in decisions:
        a = d["action"]
        if a == "DISCARD":
            continue
        if a == "REINFORCE":
            m = next(x for x in brain.active_memories(user_id) if x["id"] == d["match_id"])
            new_c = u.reinforce(m["confidence"])
            brain.update_memory(d["match_id"], confidence=new_c, last_affirmed=u.now())
            applied.append({**d, "confidence": round(new_c, 3)})
        elif a == "WEAK_CONTRADICTION":
            m = next(x for x in brain.active_memories(user_id) if x["id"] == d["match_id"])
            new_c = u.contradict(m["confidence"])
            brain.update_memory(d["match_id"], confidence=new_c)
            applied.append({**d, "confidence": round(new_c, 3)})
        else:                                    # CREATE / COEXIST / SUPERSEDE
            conf = max(d["parts"]["extraction"], C.SUPERSEDE_FLOOR) if a == "SUPERSEDE" \
                else d["parts"]["extraction"]
            m = brain.add_memory(user_id, d["type"], d["value"], d["topic"],
                                 conf, message, session_id)
            if a == "SUPERSEDE":
                brain.supersede(d["match_id"], m["id"])
            applied.append({**d, "memory_id": m["id"], "confidence": round(conf, 3)})
    return applied
