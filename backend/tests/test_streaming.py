"""Streaming must deliver the same result as the blocking path, only sooner."""
import pytest

from modules.chat.orchestrator import handle, handle_stream
from modules.llm.base import LLMError
from modules.llm.registry import stream

MSG = "I am planning to switch jobs next year"
collect = lambda gen: [(k, p) for k, p in gen]


def test_every_provider_exposes_a_stream():
    from modules.llm.registry import PROVIDERS
    for name, cls in PROVIDERS.items():
        assert callable(getattr(cls, "stream", None)), f"{name} cannot stream"


def test_registry_emits_meta_before_any_token():
    events = collect(stream([{"role": "user", "content": "hi"}], provider="mock"))
    assert events[0][0] == "meta"
    assert all(k == "token" for k, _ in events[1:])
    assert events[0][1]["provider"] == "mock"


def test_stream_falls_through_to_a_working_provider():
    """A provider with no key is skipped, and the skip is reported in meta."""
    events = collect(stream([{"role": "user", "content": "hi"}], chain=["openai", "mock"]))
    assert events[0][1]["provider"] == "mock"
    assert any("no-key" in t for t in events[0][1]["fallbacks_tried"])


def test_stream_yields_context_then_tokens_then_done(brain, sessions, rahul):
    kinds = [k for k, _ in collect(handle_stream(MSG, "rahul", "s1", brain, sessions,
                                                 provider="mock"))]
    assert kinds[0] == "context" and kinds[-1] == "done"
    assert kinds.count("token") > 1, "a single chunk is not streaming"


def test_context_event_carries_retrieval_before_generation(brain, sessions, rahul):
    brain.add_memory("rahul", "GOAL", "switch jobs", "career", 0.9, "src", "s0")
    _, ctx = next(iter(handle_stream("What about my career?", "rahul", "s1", brain,
                                     sessions, provider="mock")))
    steps = [s["step"] for s in ctx["steps"]]
    assert steps == ["understand", "retrieve", "build_prompt"]


def test_streamed_text_matches_the_done_payload(brain, sessions, rahul):
    events = collect(handle_stream(MSG, "rahul", "s1", brain, sessions, provider="mock"))
    streamed = "".join(p for k, p in events if k == "token")
    assert streamed == events[-1][1]["response"]


def test_streaming_and_blocking_store_the_same_memory(brain, sessions, rahul):
    collect(handle_stream(MSG, "rahul", "s1", brain, sessions, provider="mock"))
    streamed = [(m["type"], m["value"]) for m in brain.active_memories("rahul")]
    brain.clear_memories("rahul")
    handle(MSG, "rahul", "s2", brain, sessions, provider="mock")
    assert streamed == [(m["type"], m["value"]) for m in brain.active_memories("rahul")]


def test_total_failure_still_produces_a_done_event(brain, sessions, rahul, monkeypatch):
    monkeypatch.setattr("modules.chat.orchestrator.stream",
                        lambda *a, **k: (_ for _ in ()).throw(LLMError("all down")))
    events = collect(handle_stream(MSG, "rahul", "s1", brain, sessions, provider="mock"))
    kind, payload = events[-1]
    assert kind == "done" and payload["degraded"] is True and payload["response"]
