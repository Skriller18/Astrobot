"""Turn -> candidate memories, via the LLM, in a strict JSON shape."""
import json

import constants as C
from modules.llm.registry import complete

PROMPT = """Extract durable facts about the USER from their message.

Types: {types}
Topics: {topics}

Rules:
- Only facts about the user themselves, never general astrology questions.
- Transient moods or one-off states are type STATE.
- value must be a short noun phrase (2-8 words), quoting the user's own words.
- Return [] when the message contains no durable fact.

Return JSON: {{"memories": [{{"type": ..., "value": ..., "topic": ...,
"confidence": 0.0-1.0, "attributes": {{}}}}]}}"""


def extract(message, provider=None, model=None):
    """Returns (candidates, error). Never raises -- extraction is best effort."""
    msgs = [{"role": "system", "content": PROMPT.format(
                types=", ".join(C.TYPES), topics=", ".join(C.TOPIC_KEYWORDS))},
            {"role": "user", "content": message}]
    try:
        resp, _ = complete(msgs, provider=provider, model=model,
                           json_mode=True, temperature=0)
        return json.loads(resp.text).get("memories", []), None
    except Exception as e:                       # noqa: BLE001
        return [], str(e)[:120]
