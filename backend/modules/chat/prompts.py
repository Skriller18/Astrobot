"""Prompt assembly, under an explicit token budget."""
import constants as C

SYSTEM = """You are MyNaksh, a warm and practical Vedic astrology guide.
Ground advice in the user's actual situation, not generic horoscope filler.
Be concrete and kind. Two short paragraphs at most.{language}"""


def build(user, memories, history, message):
    """Returns (messages, trace) -- trace records what went in and what was cut."""
    lang = user.get("language") if user else None
    system = SYSTEM.format(language=f"\nReply in {lang}." if lang and lang != "English" else "")

    profile = _profile_block(user)
    mem_block = "\n".join(f"- {m['type'].lower()}: {m['value']}"
                          for m in memories)[:C.MEMORY_CHARS]

    parts = [system]
    if profile:
        parts.append("User profile:\n" + profile)
    if mem_block:
        parts.append("What you remember about this user:\n" + mem_block)
    elif user:
        parts.append("You have no stored memories for this user yet.")

    msgs = [{"role": "system", "content": "\n\n".join(parts)}]
    msgs += [{"role": t["role"], "content": t["content"]} for t in history]
    msgs.append({"role": "user", "content": message})

    trace = {"budget": C.BUDGET,
             "approx_tokens": sum(len(m["content"]) for m in msgs) // 4,
             "profile_included": bool(profile), "memories_included": len(memories),
             "history_turns": len(history)}
    return msgs, trace


def _profile_block(user):
    if not user:
        return ""
    rows = [(k, user.get(k)) for k in ("name", "dob", "tob", "birth_place", "zodiac", "element")]
    return "\n".join(f"- {k}: {v}" for k, v in rows if v)


def missing_profile(user):
    return [f for f in ("name", "dob", "birth_place") if not (user or {}).get(f)]
