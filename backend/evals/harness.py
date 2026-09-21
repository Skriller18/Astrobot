"""Shared plumbing: load datasets, override constants, seed a brain."""
import contextlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

import constants as C                                    # noqa: E402
import utils as u                                        # noqa: E402
from modules.brain.store import MemoryBrain              # noqa: E402

DATASETS, RESULTS = ROOT / "datasets", ROOT / "results"


def load(name):
    return json.loads((DATASETS / f"set_{name}.json").read_text())


@contextlib.contextmanager
def config(**overrides):
    """Temporarily patch constants so one run can be scored under one config."""
    before = {k: getattr(C, k) for k in overrides}
    for k, v in overrides.items():
        setattr(C, k, v)
    try:
        yield
    finally:
        for k, v in before.items():
            setattr(C, k, v)


def seeded_brain(user="eval_user"):
    """A fixed brain built from Set B, so retrieval runs are comparable."""
    brain = MemoryBrain()
    brain.upsert_user(user, name="Rahul", dob="1995-08-15", birth_place="Delhi")
    for m in load("b")["seed"]:
        node = brain.add_memory(user, m["type"], m["value"], m["topic"],
                                m["confidence"], "seeded", "seed")
        # re-key to the dataset's stable id so labels can refer to it
        stored = brain.memories.pop(node["id"])
        stored["id"] = m["id"]
        brain.memories[m["id"]] = stored
    return brain, user


def save(name, payload):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(payload, indent=1, default=str))
    return RESULTS / f"{name}.json"


def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0
