"""Unit tests for the formula sheet (docs/architecture.md section 8)."""
import constants as C
import utils as u


def test_durability_orders_types_by_half_life():
    order = ["EVENT", "GOAL", "INTEREST", "ATTRIBUTE", "PREFERENCE", "IDENTITY"]
    vals = [u.durability(t) for t in order]
    assert vals == sorted(vals) and vals[-1] == 1.0


def test_promotion_matches_the_documented_calibration():
    cases = [("ATTRIBUTE", "engineer in Bangalore", "career", True, 0.83),
             ("GOAL", "product management by 2027", "career", True, 0.78),
             ("EVENT", "tea at 4pm", "", True, 0.55)]
    for mtype, value, topic, qual, expected in cases:
        score, _ = u.promotion_score(mtype, value, topic, value, has_qualifier=qual)
        assert abs(score - expected) < 0.02, f"{value}: {score:.3f} != {expected}"


def test_only_topic_supported_rejects_well_formed_trivia():
    """The rejection is carried entirely by utility -- see docs section 8.10."""
    on, _ = u.promotion_score("EVENT", "job interview last week", "career", "x", has_qualifier=True)
    off, _ = u.promotion_score("EVENT", "tea at four pm", "", "x", has_qualifier=True)
    assert on >= C.PROMOTION_THRESHOLD > off


def test_reinforce_is_asymptotic_and_never_exceeds_one():
    c = 0.6
    for _ in range(50):
        c = u.reinforce(c)
    assert c < 1.0 and u.reinforce(0.99) > 0.99


def _hits_to_sink(mtype, start=0.9):
    """How many contradictions until this memory stops clearing the retrieval floor."""
    c, n = start, 0
    while c * C.TYPES[mtype]["imp"] >= C.RETRIEVAL_FLOOR and n < 20:
        c, n = u.contradict(c), n + 1
    return n


def test_low_importance_memories_sink_sooner_than_high_importance_ones():
    """The design claim is the *ordering*, not an absolute count -- how many hits it
    takes depends on RETRIEVAL_FLOOR, which the eval sweep tunes."""
    assert _hits_to_sink("EVENT") <= _hits_to_sink("GOAL") <= _hits_to_sink("IDENTITY")
    assert _hits_to_sink("EVENT") < 20, "contradiction must eventually sink a memory"


def test_decay_halves_at_one_half_life():
    from datetime import timedelta
    past = u.now() - timedelta(days=int(C.TYPES["GOAL"]["half_life"] * 30.44))
    assert abs(u.decay("GOAL", past) - 0.5) < 0.02
    assert u.decay("IDENTITY", past) == 1.0


def test_relevance_lets_either_channel_surface_a_memory():
    assert u.relevance(1.0, 0.0) == 1.0          # topic hit, vector miss
    assert u.relevance(0.0, 0.95) == 1.0         # vector hit, topic miss


def test_cosine_rescale_zeroes_the_uninformative_band():
    assert u.rescaled_cos(0.50) == 0.0 and u.rescaled_cos(0.95) == 1.0


def test_cardinality_not_similarity_authorises_a_supersede():
    same = dict(value_differs=True, same_slot=True)
    assert u.match_action(0.60, is_single=True, **same) == "SUPERSEDE"
    assert u.match_action(0.60, is_single=False, **same) == "COEXIST"
    assert u.match_action(0.95, is_single=True, **same) == "REINFORCE"
    # a different slot is not a contradiction, however similar the wording
    assert u.match_action(0.60, is_single=True, value_differs=True, same_slot=False) != "SUPERSEDE"


def test_followup_detection_is_about_shape_not_position():
    prior = ["your career goal is to switch jobs"]
    assert u.is_followup("Why do you say that?", prior)
    assert not u.is_followup("What does my birth chart say about marriage?", prior)


def test_sun_sign_boundaries():
    assert u.sun_sign("1995-08-15") == "Leo" and u.element("Leo") == "Fire"
    assert u.sun_sign("1995-01-01") == "Capricorn"
    assert u.sun_sign("not-a-date") is None


def test_requests_are_not_facts_even_without_a_question_mark():
    """Imperatives and inverted questions are requests, not assertions about the user."""
    rejected = ["Tell me what my chart says about money",
                "Show me my career outlook",
                "Should I switch jobs next year",
                "What does my zodiac mean for me",
                "Can you explain my birth chart"]
    for msg in rejected:
        assert not u.passes_gates(msg, "GOAL", "something"), f"should reject: {msg}"


def test_genuine_assertions_still_pass_the_gates():
    accepted = ["I am planning to switch jobs next year",
                "My name is Rahul and I live in Delhi",
                "I prefer replies in Hindi",
                "I work as a product manager"]
    for msg in accepted:
        assert u.passes_gates(msg, "GOAL", "switch jobs"), f"should accept: {msg}"
