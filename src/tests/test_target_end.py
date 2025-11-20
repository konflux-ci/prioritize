from rules.program.target_end import check_target_end_date, listify
from tests.conftest import MockIssue


def make_epics(keys):
    return [MockIssue(key, "TEST", None, 0) for key in keys]


def make_child_with_target_date(key, status, status_category, target_date):
    """Helper to create a child issue with a target date."""
    child = MockIssue(
        key, "RELEASE", None, 0, status=status, status_category=status_category
    )
    child.raw["Context"]["Field Ids"]["Target End Date"] = "customfield_12345"
    setattr(child.fields, "customfield_12345", target_date)
    return child


def make_parent_with_children(key, children):
    """Helper to create a parent feature with children."""
    parent = MockIssue(key, "KONFLUX", None, 0)
    parent.raw["Context"]["Field Ids"]["Target End Date"] = "customfield_12345"
    parent.raw["Context"]["Related Issues"]["Children"] = children
    setattr(parent.fields, "customfield_12345", None)
    return parent


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


def test_target_end_date_with_release_pending():
    """Test that Release Pending children are included in target date calculation.

    Replicates KONFLUX-6027: child with status="Release Pending" should contribute
    its target date to the parent, even though statusCategory="Done".
    """
    closed = make_child_with_target_date("RELEASE-1313", "Closed", "Done", "2025-01-15")
    pending = make_child_with_target_date(
        "RELEASE-1571", "Release Pending", "Done", "2025-02-28"
    )
    parent = make_parent_with_children("KONFLUX-6027", [closed, pending])

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # Should propagate the date from Release Pending child (not Closed child)
    assert len(context["updates"]) == 1
    assert "2025-02-28" in context["updates"][0]
    assert "RELEASE-1571" in context["updates"][0]


def test_target_end_date_all_done_children_excluded():
    """Test that truly Done children (not Release Pending) are excluded."""
    closed = make_child_with_target_date("RELEASE-100", "Closed", "Done", "2025-01-15")
    done = make_child_with_target_date("RELEASE-101", "Done", "Done", "2025-01-20")
    parent = make_parent_with_children("KONFLUX-1234", [closed, done])
    setattr(parent.fields, "customfield_12345", "2025-01-10")  # Has existing date

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # All children are Done (not Release Pending), so target date should clear
    assert len(context["updates"]) == 1
    assert "None" in context["updates"][0]


def test_target_end_date_mixed_children():
    """Test with mix of In Progress, Release Pending, and Done children."""
    in_progress = make_child_with_target_date(
        "RELEASE-200", "In Progress", "In Progress", "2025-03-15"
    )
    pending = make_child_with_target_date(
        "RELEASE-201", "Release Pending", "Done", "2025-04-30"
    )
    closed = make_child_with_target_date("RELEASE-202", "Closed", "Done", "2025-01-01")
    parent = make_parent_with_children("KONFLUX-5678", [in_progress, pending, closed])

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # Should use latest date from In Progress + Release Pending (exclude Closed)
    assert len(context["updates"]) == 1
    assert "2025-04-30" in context["updates"][0]
    assert "RELEASE-201" in context["updates"][0]
