"""Every formula in the system. Pure functions, no I/O, no state.

Mirrors docs/architecture.md section 8 one-to-one so the doc stays checkable.
"""
import hashlib, math, re
from datetime import datetime, timezone

import constants as C

# ----------------------------------------------------------------------- basic
now = lambda: datetime.now(timezone.utc)
tokens = lambda s: re.findall(r"[a-z0-9]+", (s or "").lower())
def stem(t):
    """ponytail: plural-only stemmer. Handles -ies and -s, skips -ss.

    Found by a live session: "studies" stemmed to "studie" and never matched the
    lexicon's "study", so an education question retrieved nothing.
    """
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


stems = lambda s: {stem(t) for t in tokens(s)}


def months_between(a, b=None):
    return max(0.0, ((b or now()) - a).total_seconds() / 2_629_746)  # avg month


def embed(text):
    """Hashed bag-of-words unit vector.

    ponytail: deterministic and offline; swap for a real embedding model when
    paraphrase recall matters more than zero dependencies.
    """
    v = [0.0] * C.EMBED_DIM
    for t in tokens(text):
        v[int(hashlib.md5(t.encode()).hexdigest(), 16) % C.EMBED_DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) if a and b else 0.0


# ------------------------------------------------------------------- 8.3 promotion
def durability(mtype):
    hl = C.TYPES[mtype]["half_life"]
    return 1.0 if hl is None else hl / (hl + C.DURABILITY_HORIZON)


def specificity(value, has_qualifier):
    w, n = C.SPECIFICITY_WEIGHTS, len(tokens(value))
    concrete = 1.0 if n and not _is_sentiment(value) else 0.0
    length_ok = 1.0 if C.VALUE_TOKEN_BAND[0] <= n <= C.VALUE_TOKEN_BAND[1] else 0.0
    return w["concrete"] * concrete + w["qualifier"] * float(has_qualifier) + w["length"] * length_ok


_SENTIMENT = {"good", "better", "happy", "fine", "nice", "ok", "great", "bad", "sad"}
_is_sentiment = lambda v: set(tokens(v)) <= _SENTIMENT


def topic_supported(topic):
    if topic in C.CORE_TOPICS:
        return 1.0
    return 0.5 if topic in C.ADJACENT_TOPICS else 0.0


def utility(mtype, topic):
    w = C.UTILITY_TOPIC_WEIGHT
    return w * topic_supported(topic) + (1 - w) * C.TYPES[mtype]["util"]


def grounding(value, source):
    tv = set(tokens(value))
    return len(tv & set(tokens(source))) / len(tv) if tv else 0.0


def extraction_conf(self_report, value, source, slots_complete):
    w = C.EXTRACTION_WEIGHTS
    return (w["self_report"] * self_report + w["grounding"] * grounding(value, source)
            + w["slots"] * float(slots_complete))


def promotion_score(mtype, value, topic, source, self_report=0.8,
                    has_qualifier=False, slots_complete=True):
    """Weighted sum: gates already vetoed, so dimensions trade off here."""
    w = C.PROMOTION_WEIGHTS
    parts = {
        "durability": durability(mtype),
        "specificity": specificity(value, has_qualifier),
        "utility": utility(mtype, topic),
        "extraction": extraction_conf(self_report, value, source, slots_complete),
    }
    return sum(w[k] * v for k, v in parts.items()), parts


# --------------------------------------------------------------------- 8.3 gates
_FIRST_PERSON = re.compile(r"\b(i|i'm|im|my|mine|me|myself|we|our)\b")
# A request is not an assertion. Checking only for a trailing "?" misses imperatives
# ("Tell me about my career") and inverted questions ("Should I switch jobs"), both of
# which are self-referential and would otherwise be promoted as facts.
_REQUEST = re.compile(
    r"^(tell|show|give|explain|describe|list|suggest|recommend|help|predict|"
    r"what|when|where|why|how|who|which|whose|"
    r"is|are|was|were|do|does|did|can|could|would|should|shall|will|may|might)\b")
_QUALIFIER = re.compile(r"\b(\d{4}|\d+|next|last|this)\s*(year|month|week|day)?\b|\b[A-Z][a-z]{2,}\b")


def passes_gates(message, mtype, value):
    """Self-referential AND declarative AND resolvable AND not a STATE."""
    text = message.strip().lower()
    return all([
        bool(_FIRST_PERSON.search(text)),
        not text.endswith("?") and not _REQUEST.match(text),
        bool(value) and not _is_sentiment(value),
        mtype in C.PROMOTABLE,
    ])


has_qualifier = lambda text: bool(_QUALIFIER.search(text or ""))


# ------------------------------------------------------------------- 8.4 matching
def match_action(sim, is_single, value_differs, same_slot=False):
    """Cardinality, not similarity, is what authorises a supersede.

    A single-valued slot (city, language, marital status) can hold one value, so a
    different value for the same slot replaces it however the embedder scores them.
    Similarity only decides same-meaning (reinforce) and unrelated (create).
    """
    if sim >= C.SIM_SAME:
        return "REINFORCE"
    if is_single and same_slot and value_differs:
        return "SUPERSEDE"
    if sim < C.SIM_RELATED:
        return "CREATE"
    return "COEXIST" if not is_single else "WEAK_CONTRADICTION"


# ----------------------------------------------------------------- 8.5 confidence
reinforce = lambda c: c + C.REINFORCE_RATE * (1 - c)
contradict = lambda c: c * C.CONTRADICT_FACTOR


# ---------------------------------------------------------------------- 8.6 decay
def decay(mtype, last_affirmed):
    hl = C.TYPES[mtype]["half_life"]
    return 1.0 if hl is None else 0.5 ** (months_between(last_affirmed) / hl)


# ------------------------------------------------------------------ 8.7 retrieval
def rescaled_cos(sim):
    lo, hi = C.COSINE_BAND
    return min(1.0, max(0.0, (sim - lo) / (hi - lo)))


def topic_match(query_topics, memory_topic):
    if not memory_topic:
        return C.TOPIC_MATCH_SCORES["none"]
    if memory_topic in query_topics:
        return C.TOPIC_MATCH_SCORES["exact"]
    same_family = any(t in C.CORE_TOPICS for t in query_topics) and memory_topic in C.CORE_TOPICS
    return C.TOPIC_MATCH_SCORES["sibling"] if same_family else C.TOPIC_MATCH_SCORES["none"]


relevance = lambda tm, sim: max(tm, rescaled_cos(sim))


def retrieval_score(rel, confidence, mtype, last_affirmed):
    """Product, not sum: relevance must be able to veto."""
    return rel * confidence * C.TYPES[mtype]["imp"] * decay(mtype, last_affirmed)


# ------------------------------------------------------------------ 8.8 follow-up
def followup_score(message, recent_turns):
    w, tk = C.FOLLOWUP_WEIGHTS, tokens(message)
    seen = set(t for turn in recent_turns[-2:] for t in tokens(turn))
    return (w["no_new_content"] * float(bool(tk) and set(tk) <= seen | C.ANAPHORA)
            + w["anaphora"] * float(bool(set(tk) & C.ANAPHORA))
            + w["short"] * float(len(tk) <= C.FOLLOWUP_SHORT_TOKENS)
            + w["why"] * float(message.lower().strip().startswith(C.WHY_OPENERS)))


is_followup = lambda msg, turns: followup_score(msg, turns) >= C.FOLLOWUP_THRESHOLD


# ------------------------------------------------------------------ 8.9 astrology
def sun_sign(dob):
    """dob as YYYY-MM-DD. ponytail: date-range lookup, not ephemeris maths."""
    try:
        d = datetime.strptime(dob[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return next(s for m, day, s in C.ZODIAC if (d.month, d.day) <= (m, day))


element = lambda sign: C.ELEMENTS.get(sign)


# ------------------------------------------------------------- topic classification
def classify_topics(text):
    """Keyword lexicon. Cheap, deterministic, and the pre-filter before any LLM."""
    tk = stems(text)
    hits = [(t, len(tk & stems(kw))) for t, kw in C.TOPIC_KEYWORDS.items()]
    return [t for t, n in sorted(hits, key=lambda x: -x[1]) if n > 0]
