"""The eight scenarios named in the assignment, plus the two failure paths."""
from modules.chat.orchestrator import handle
from modules.memory.policy import apply, evaluate

GOAL_MSG = "I'm planning to switch jobs next year"
ask = lambda msg, b, s, sid="s1", uid="rahul": handle(msg, uid, sid, b, s, provider="mock")
step = lambda r, name: next(x for x in r["trace"]["steps"] if x["step"] == name)


def test_1_new_user_gets_created_and_asked_for_details(brain, sessions):
    r = ask("Hello", brain, sessions, uid="stranger")
    assert brain.get_user("stranger") is not None
    assert set(r["missing_profile"]) == {"name", "dob", "birth_place"}


def test_2_durable_statement_becomes_a_long_term_memory(brain, sessions, rahul):
    ask(GOAL_MSG, brain, sessions)
    mems = brain.active_memories("rahul")
    assert len(mems) == 1 and mems[0]["type"] == "GOAL" and mems[0]["topic"] == "career"


def test_3_memory_is_retrieved_for_a_related_question(brain, sessions, rahul):
    ask(GOAL_MSG, brain, sessions)
    r = ask("What should I focus on for my career?", brain, sessions)
    assert step(r, "retrieve")["selected"], "the stored goal should have been selected"
    assert len(r["context_used"]) > 1


def test_4_followup_uses_conversation_not_the_graph(brain, sessions, rahul):
    ask(GOAL_MSG, brain, sessions)
    ask("What should I focus on for my career?", brain, sessions)
    r = ask("Why do you say that?", brain, sessions)
    assert step(r, "understand")["is_followup"] is True
    assert step(r, "retrieve")["skipped"] is True


def test_5_new_session_still_knows_the_goal(brain, sessions, rahul):
    ask(GOAL_MSG, brain, sessions, sid="s1")
    r = ask("What do you remember about my career goals?", brain, sessions, sid="s2")
    assert step(r, "retrieve")["selected"], "long-term memory should survive the session"
    assert not sessions.last_turns("s2")[:-2], "new session starts with an empty window"


def test_6_irrelevant_chatter_is_not_stored(brain, sessions, rahul):
    ask("I had tea at 4pm", brain, sessions)
    assert brain.active_memories("rahul") == []


def test_7_correction_supersedes_a_single_valued_memory(brain, sessions, rahul):
    m = brain.add_memory("rahul", "ATTRIBUTE", "living in Delhi", "travel", 0.9, "src", "s1")
    msg = "I am moving to Bangalore"
    dec = evaluate([{"type": "ATTRIBUTE", "value": "living in Bangalore",
                     "topic": "travel", "confidence": 0.9}], msg, brain.active_memories("rahul"))
    apply(dec, brain, "rahul", msg, "s1")
    assert brain.memories[m["id"]]["status"] == "superseded"
    assert [x["value"] for x in brain.active_memories("rahul")] == ["living in Bangalore"]


def test_8_multi_valued_goals_coexist_instead_of_overwriting(brain, sessions, rahul):
    brain.add_memory("rahul", "GOAL", "get a promotion", "career", 0.9, "src", "s1")
    msg = "I also want to start my own company"
    dec = evaluate([{"type": "GOAL", "value": "start my own company",
                     "topic": "career", "confidence": 0.9}], msg, brain.active_memories("rahul"))
    apply(dec, brain, "rahul", msg, "s1")
    assert len(brain.active_memories("rahul")) == 2, "two career goals are both true"


def test_9_llm_failure_degrades_instead_of_crashing(brain, sessions, rahul, monkeypatch):
    from modules.llm.base import LLMError
    monkeypatch.setattr("modules.chat.orchestrator.complete",
                        lambda *a, **k: (_ for _ in ()).throw(LLMError("all down")))
    r = handle("What about my career?", "rahul", "s1", brain, sessions, provider="mock")
    assert r["degraded"] is True and r["response"]


def test_10_no_relevant_context_is_a_real_outcome(brain, sessions, rahul):
    brain.add_memory("rahul", "GOAL", "switch jobs", "career", 0.9, "src", "s1")
    r = ask("Tell me about my health", brain, sessions)
    assert not step(r, "retrieve")["selected"], "a career goal must not answer a health question"
