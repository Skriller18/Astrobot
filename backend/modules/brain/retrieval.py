"""Select the small slice of the brain that this question needs."""
import constants as C
import utils as u


def select(message, memories, topics):
    """Score every active memory, keep those above the floor. Returns (kept, all_scored)."""
    q = u.embed(message)
    scored = []
    for m in memories:
        tm = u.topic_match(topics, m.get("topic"))
        sim = u.cosine(q, m.get("embedding") or [])
        rel = u.relevance(tm, sim)
        score = u.retrieval_score(rel, m["confidence"], m["type"], m["last_affirmed"])
        scored.append({
            "id": m["id"], "type": m["type"], "value": m["value"], "topic": m.get("topic"),
            "topic_match": round(tm, 2), "cosine": round(sim, 3),
            "relevance": round(rel, 3), "confidence": round(m["confidence"], 3),
            "importance": C.TYPES[m["type"]]["imp"],
            "decay": round(u.decay(m["type"], m["last_affirmed"]), 3),
            "score": round(score, 3), "included": False})
    scored.sort(key=lambda s: -s["score"])
    kept = [s for s in scored if s["score"] >= C.RETRIEVAL_FLOOR][:C.TOP_K]
    for s in kept:
        s["included"] = True
    return kept, scored
