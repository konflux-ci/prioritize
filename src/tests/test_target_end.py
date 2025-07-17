from rules.program.target_end import listify
from tests.conftest import MockIssue


def make_epics(keys):
    return [MockIssue(key, "TEST", None, 0) for key in keys]


def test_listify_empty():
    empty = listify([])
    assert empty == ""


def test_listify_single():
    epics = make_epics(["E-1"])
    assert listify(epics) == "E-1"


def test_listify_two():
    epics = make_epics(["E-1", "E-2"])
    assert listify(epics) == "E-1 and E-2"


def test_listify_multiple():
    epics = make_epics(["E-1", "E-2", "E-3"])
    assert listify(epics) == "E-1, E-2 and E-3"
    epics = make_epics(["A", "B", "C", "D"])
    assert listify(epics) == "A, B, C and D"
