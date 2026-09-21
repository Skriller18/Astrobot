"""Provider contract. Every provider returns the same shape and raises the same error."""
from dataclasses import dataclass, field


class LLMError(RuntimeError):
    """Any provider failure: network, auth, rate limit, bad response."""


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: dict = field(default_factory=dict)


class LLMProvider:
    name = "base"
    default_model = ""

    def __init__(self, api_key=None, model=None, base_url=None):
        self.api_key, self.model = api_key, model or self.default_model
        self.base_url = base_url

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        """messages: [{"role": "system"|"user"|"assistant", "content": str}]"""
        raise NotImplementedError

    def stream(self, messages, temperature=0.7, max_tokens=800):
        """Yield text deltas as they arrive.

        The default just emits the finished reply in one piece, so a provider
        without streaming still satisfies the interface.
        """
        yield self.complete(messages, temperature, max_tokens).text

    @property
    def available(self):
        return bool(self.api_key)

    # shared helpers -------------------------------------------------------
    @staticmethod
    def split_system(messages):
        """Anthropic and Gemini take the system prompt out of band."""
        sys = " ".join(m["content"] for m in messages if m["role"] == "system")
        return sys, [m for m in messages if m["role"] != "system"]
