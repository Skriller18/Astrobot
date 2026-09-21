"""The eval harness itself needs to be trustworthy before its numbers mean anything."""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "evals"))

import constants as C
import tier1, tier2
from harness import config, load, seeded_brain


def test_set_a_is_roughly_half_negatives():
    """A golden set of easy positives proves nothing -- refusing is the hard part."""
    rows = load("a")["simple"]
    discard = sum(1 for r in rows if r["decision"] == "DISCARD")
    assert 0.4 <= discard / len(rows) <= 0.65, f"{discard}/{len(rows)} negatives"


def test_set_b_includes_questions_that_should_retrieve_nothing():
    empty = [q for q in load("b")["queries"] if not q["expect"]]
    assert len(empty) >= 5, "without these the retrieval floor is never tested"


def test_seeded_brain_keeps_the_dataset_ids():
    brain, user = seeded_brain()
    ids = {m["id"] for m in brain.active_memories(user)}
    assert {m["id"] for m in load("b")["seed"]} == ids


def test_config_override_restores_the_original_value():
    before = C.PROMOTION_THRESHOLD
    with config(PROMOTION_THRESHOLD=0.9):
        assert C.PROMOTION_THRESHOLD == 0.9
    assert C.PROMOTION_THRESHOLD == before


def test_tier1_scores_every_row():
    r = tier1.run()
    assert r["metrics"]["n"] == len(load("a")["simple"])
    assert 0 <= r["metrics"]["accuracy_pct"] <= 100


def test_tier2_scores_every_query():
    r = tier2.run()
    assert r["metrics"]["n"] == len(load("b")["queries"])


def test_a_higher_threshold_stores_strictly_less():
    """Sanity check on the sweep: the knob must move the metric in one direction."""
    with config(PROMOTION_THRESHOLD=0.4):
        loose = tier1.run()["metrics"]["junk_stored"]
    with config(PROMOTION_THRESHOLD=0.9):
        strict = tier1.run()["metrics"]["junk_stored"]
    assert strict <= loose


def test_a_higher_floor_retrieves_strictly_less():
    with config(RETRIEVAL_FLOOR=0.05):
        loose = tier2.run()["metrics"]["avg_injected"]
    with config(RETRIEVAL_FLOOR=0.9):
        strict = tier2.run()["metrics"]["avg_injected"]
    assert strict < loose
