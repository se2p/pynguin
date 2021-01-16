import os

import pytest

from pynguin.analyses.seeding.dynamicseeding import DynamicSeeding
from pynguin.analyses.seeding.dynamicseedinginstrumentation import DynamicSeedingInstrumentation


@pytest.fixture
def dynamic_seeding():
    dynamic_seeding = DynamicSeeding()
    return dynamic_seeding


@pytest.fixture
def fixture_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "fixtures",
        "seeding",
    )


def test_singleton():
    dynamic_seeding_1 = DynamicSeeding()
    dynamic_seeding_2 = DynamicSeeding()
    assert dynamic_seeding_1 is dynamic_seeding_2

def test_isalnum_instrumentation():
    instr = DynamicSeedingInstrumentation()
