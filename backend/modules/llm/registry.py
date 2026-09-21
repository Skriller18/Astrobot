"""Pick a provider by name, fall through the chain on failure."""
import constants as C
from modules.llm.base import LLMError
from modules.llm.providers.http_providers import (AnthropicProvider, GeminiProvider,
                                                  MockProvider, OllamaProvider,
                                                  OpenAIProvider, OpenRouterProvider)

PROVIDERS = {p.name: p for p in (OpenAIProvider, AnthropicProvider, GeminiProvider,
                                 OpenRouterProvider, OllamaProvider, MockProvider)}


def get_provider(name, model=None):
    if name not in PROVIDERS:
        raise LLMError(f"unknown provider '{name}'")
    return PROVIDERS[name](model=model)


def available_providers():
    return {n: {"available": PROVIDERS[n]().available, "models": C.PROVIDER_MODELS[n]}
            for n in PROVIDERS}


def _order(provider, chain):
    order = [provider] if provider else []
    return order + [p for p in (chain or C.DEFAULT_FALLBACK) if p != provider]


def stream(messages, provider=None, model=None, chain=None, **kw):
    """Yield ("meta", {...}) once, then ("token", text) repeatedly.

    Falls through the chain only until the first token arrives -- after that the
    client already has partial output, so a mid-stream failure ends the stream
    rather than restarting it with a different provider.
    """
    tried = []
    for name in _order(provider, chain):
        p = PROVIDERS[name](model=model if name == provider else None)
        if not p.available:
            tried.append(f"{name}:no-key")
            continue
        started = False
        try:
            for delta in p.stream(messages, **kw):
                if not started:
                    started = True
                    yield "meta", {"provider": p.name, "model": p.model, "fallbacks_tried": tried}
                yield "token", delta
            if started:
                return
            tried.append(f"{name}:empty")
        except LLMError as e:
            if started:
                yield "error", f"{name} failed mid-stream: {str(e)[:80]}"
                return
            tried.append(f"{name}:{str(e)[:60]}")
    raise LLMError(f"all providers failed: {tried}")


def complete(messages, provider=None, model=None, chain=None, **kw):
    """Try the named provider, then each fallback. Returns (response, tried)."""
    tried = []
    for name in _order(provider, chain):
        p = PROVIDERS[name](model=model if name == provider else None)
        if not p.available:
            tried.append(f"{name}:no-key")
            continue
        try:
            return p.complete(messages, **kw), tried
        except LLMError as e:
            tried.append(f"{name}:{str(e)[:60]}")
    raise LLMError(f"all providers failed: {tried}")
