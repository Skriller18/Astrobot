"""Profile CRUD. Astrology attributes are derived, never stored by hand."""
import utils as u
from modules.brain.store import PROFILE_FIELDS


def upsert(brain, user_id, payload):
    return brain.upsert_user(user_id, **{k: payload.get(k) for k in PROFILE_FIELDS})


def get(brain, user_id):
    user = brain.get_user(user_id)
    if user and user.get("dob") and not user.get("zodiac"):
        user["zodiac"] = u.sun_sign(user["dob"])
        user["element"] = u.element(user["zodiac"])
    return user
