import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(BRAIN="memory", SESSIONS="memory")

import pytest

from modules.brain.store import MemoryBrain
from modules.session.store import MemorySessions


@pytest.fixture
def brain():
    return MemoryBrain()


@pytest.fixture
def sessions():
    return MemorySessions()


@pytest.fixture
def rahul(brain):
    return brain.upsert_user("rahul", name="Rahul", dob="1995-08-15",
                             birth_place="Delhi", language="English")
