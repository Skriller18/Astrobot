"""All five real providers. One httpx call each.

ponytail: raw HTTP over five vendor SDKs -- the request bodies are a few lines
and this keeps the dependency list at one entry instead of five.
"""
import json, time

import httpx

import constants as C
from modules.llm.base import LLMError, LLMProvider, LLMResponse


def _post(url, headers, body, timeout=C.LLM_TIMEOUT):
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:                      # noqa: BLE001 - one error type upward
        raise LLMError(f"{url.split('/')[2]}: {e}") from e


def _sse(url, headers, body, pick, timeout=C.LLM_TIMEOUT):
    """Stream a server-sent-event response, mapping each JSON payload via `pick`.

    `pick` returns the text delta for one event, or None to skip it.
    """
    try:
        with httpx.stream("POST", url, headers=headers, json=body, timeout=timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    delta = pick(json.loads(data))
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    continue
                if delta:
                    yield delta
    except LLMError:
        raise
    except Exception as e:                      # noqa: BLE001
        raise LLMError(f"{url.split('/')[2]} stream: {e}") from e


class OpenAIProvider(LLMProvider):
    name, default_model = "openai", "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key=None, model=None, base_url=None):
        super().__init__(api_key or C.API_KEYS["openai"], model, base_url)

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        body = {"model": self.model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        d = _post(self.base_url or self.url,
                  {"Authorization": f"Bearer {self.api_key}"}, body)
        return LLMResponse(d["choices"][0]["message"]["content"], self.model,
                           self.name, d.get("usage", {}))

    def stream(self, messages, temperature=0.7, max_tokens=800):
        body = {"model": self.model, "messages": messages, "temperature": temperature,
                "max_tokens": max_tokens, "stream": True}
        yield from _sse(self.base_url or self.url,
                        {"Authorization": f"Bearer {self.api_key}"}, body,
                        lambda d: d["choices"][0]["delta"].get("content"))


class OpenRouterProvider(OpenAIProvider):
    """OpenAI-compatible, so only the endpoint, key and model list differ."""
    name, default_model = "openrouter", "anthropic/claude-sonnet-5"
    url = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key=None, model=None, base_url=None):
        LLMProvider.__init__(self, api_key or C.API_KEYS["openrouter"], model, base_url)


class AnthropicProvider(LLMProvider):
    name, default_model = "anthropic", "claude-sonnet-5"
    url = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key=None, model=None, base_url=None):
        super().__init__(api_key or C.API_KEYS["anthropic"], model, base_url)

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        system, msgs = self.split_system(messages)
        body = {"model": self.model, "messages": msgs, "max_tokens": max_tokens,
                "temperature": temperature}
        if system:
            body["system"] = system
        d = _post(self.base_url or self.url,
                  {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, body)
        return LLMResponse(d["content"][0]["text"], self.model, self.name, d.get("usage", {}))

    def stream(self, messages, temperature=0.7, max_tokens=800):
        system, msgs = self.split_system(messages)
        body = {"model": self.model, "messages": msgs, "max_tokens": max_tokens,
                "temperature": temperature, "stream": True}
        if system:
            body["system"] = system
        # Anthropic sends several event types; only content_block_delta carries text.
        yield from _sse(self.base_url or self.url,
                        {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, body,
                        lambda d: d.get("delta", {}).get("text")
                        if d.get("type") == "content_block_delta" else None)


class GeminiProvider(LLMProvider):
    """Gemini 3.x Flash are thinking models: reasoning tokens are billed against
    maxOutputTokens, so a small budget yields an empty `content` and
    finishReason MAX_TOKENS. We set thinking_level LOW and floor the budget."""
    name, default_model = "gemini", "gemini-3.8-flash"
    THINKING_HEADROOM = 2048

    def __init__(self, api_key=None, model=None, base_url=None):
        super().__init__(api_key or C.API_KEYS["gemini"], model, base_url)

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        system, msgs = self.split_system(messages)
        body = {
            "contents": [{"role": "model" if m["role"] == "assistant" else "user",
                          "parts": [{"text": m["content"]}]} for m in msgs],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens + self.THINKING_HEADROOM,
                "thinkingConfig": {"thinkingLevel": "LOW"},
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.api_key}")
        d = _post(url, {}, body)
        return LLMResponse(self._text(d), self.model, self.name, d.get("usageMetadata", {}))

    @staticmethod
    def _text(d):
        """Turn an empty candidate into a clear error instead of a KeyError."""
        cand = (d.get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise LLMError(f"gemini returned no text (finishReason="
                           f"{cand.get('finishReason')}, thinking consumed the budget)")
        return text

    def stream(self, messages, temperature=0.7, max_tokens=800):
        system, msgs = self.split_system(messages)
        body = {
            "contents": [{"role": "model" if m["role"] == "assistant" else "user",
                          "parts": [{"text": m["content"]}]} for m in msgs],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens + self.THINKING_HEADROOM,
                "thinkingConfig": {"thinkingLevel": "LOW"},
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:streamGenerateContent?alt=sse&key={self.api_key}")
        yield from _sse(url, {}, body, lambda d: "".join(
            p.get("text", "") for p in
            (d.get("candidates") or [{}])[0].get("content", {}).get("parts") or []))


class OllamaProvider(LLMProvider):
    """Several Ollama models (deepseek-v4*, glm-5.3*) are thinking models whose
    reasoning is billed against num_predict and returned in a separate `thinking`
    field, so a tight budget yields an empty `content`. Same headroom fix as Gemini."""
    name, default_model = "ollama", "deepseek-v4-flash:cloud"
    THINKING_HEADROOM = 2048

    def __init__(self, api_key=None, model=None, base_url=None):
        key = api_key or C.OLLAMA_API_KEY
        # A key means Ollama Cloud; without one we talk to the local daemon.
        super().__init__(key or "local", model,
                         base_url or (C.OLLAMA_CLOUD_URL if key else C.OLLAMA_URL))

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.api_key}"} if C.OLLAMA_API_KEY else {}

    @property
    def available(self):
        # Every model we ship is a :cloud tag, so a key is required.
        return bool(C.OLLAMA_API_KEY)

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": temperature,
                            "num_predict": max_tokens + self.THINKING_HEADROOM}}
        if json_mode:
            body["format"] = "json"
        d = _post(f"{self.base_url}/api/chat", self.headers, body)
        text = (d.get("message") or {}).get("content") or ""
        if not text:
            raise LLMError(f"ollama returned no content (done_reason="
                           f"{d.get('done_reason')}, thinking consumed the budget)")
        return LLMResponse(text, self.model, self.name, {})

    def stream(self, messages, temperature=0.7, max_tokens=800):
        """Ollama streams newline-delimited JSON rather than SSE."""
        body = {"model": self.model, "messages": messages, "stream": True,
                "options": {"temperature": temperature,
                            "num_predict": max_tokens + self.THINKING_HEADROOM}}
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=body,
                              headers=self.headers, timeout=C.LLM_TIMEOUT) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    if d.get("message", {}).get("content"):
                        yield d["message"]["content"]
                    if d.get("done"):
                        break
        except Exception as e:                   # noqa: BLE001
            raise LLMError(f"ollama stream: {e}") from e


class MockProvider(LLMProvider):
    """Deterministic. Lets the whole suite and the demo run with zero keys."""
    name, default_model = "mock", "mock-1"

    def __init__(self, api_key=None, model=None, base_url=None):
        super().__init__("mock", model, base_url)

    @property
    def available(self):
        return True

    def complete(self, messages, temperature=0.7, max_tokens=800, json_mode=False):
        system, msgs = self.split_system(messages)
        last = msgs[-1]["content"] if msgs else ""
        if json_mode:
            return LLMResponse(json.dumps(self._extract(last)), self.model, self.name)
        ctx = [l for l in system.splitlines() if l.startswith("- ")]
        body = ("Based on what I know about you (" + "; ".join(x[2:] for x in ctx) + "), "
                if ctx else "")
        return LLMResponse(f"{body}here is my reading on: {last}", self.model, self.name)

    def stream(self, messages, temperature=0.7, max_tokens=800):
        """Word-by-word, with a small delay so the UI effect is visible."""
        text = self.complete(messages, temperature, max_tokens).text
        for i, word in enumerate(text.split(" ")):
            time.sleep(C.MOCK_STREAM_DELAY)
            yield word if i == 0 else " " + word

    @staticmethod
    def _extract(text):
        """Mirror the real extractor's JSON shape with a crude rule."""
        import utils as u
        topics = u.classify_topics(text)
        if not topics or text.strip().endswith("?"):
            return {"memories": []}
        return {"memories": [{
            "type": "GOAL" if "plan" in text.lower() or "want" in text.lower() else "ATTRIBUTE",
            "value": " ".join(u.tokens(text)[:6]), "topic": topics[0],
            "confidence": 0.8, "attributes": {},
        }]}
