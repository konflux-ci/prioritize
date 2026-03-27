from rules.program.target_end import _listify, check_target_end_date
from tests.conftest import MockIssue


def make_epics(keys):
    return [MockIssue(key, "TEST", None, 0) for key in keys]


def make_child_with_target_date(key, status, target_date, issuetype="Epic"):
    """Helper to create a child issue with a target date."""
    child = MockIssue(key, "RELEASE", None, 0, status=status, issuetype=issuetype)
    child["Context"]["Field Ids"]["Target End Date"] = "customfield_12345"
    child["fields"]["customfield_12345"] = target_date
    return child


def make_parent_with_children(key, children, target_date=None):
    """Helper to create a parent feature with children."""
    parent = MockIssue(key, "KONFLUX", None, 0)
    parent["Context"]["Field Ids"]["Target End Date"] = "customfield_12345"
    parent["Context"]["Related Issues"]["Children"] = children
    parent["fields"]["customfield_12345"] = target_date
    return parent


def test_listify_empty():
    empty = _listify([])
    assert empty == "None"


def test_listify_single():
    epics = make_epics(["E-1"])
    assert _listify(epics) == "E-1"


def test_listify_two():
    epics = make_epics(["E-1", "E-2"])
    assert _listify(epics) == "E-1 and E-2"


def test_listify_multiple():
    epics = make_epics(["E-1", "E-2", "E-3"])
    assert _listify(epics) == "E-1, E-2 and E-3"
    epics = make_epics(["A", "B", "C", "D"])
    assert _listify(epics) == "A, B, C and D"


def test_target_end_date_with_release_pending():
    """Test that Release Pending children are included in target date calculation.

    Child with status="Release Pending" should contribute its target date to the parent. Only "Done" and "Closed" statuses are excluded.
    """
    closed = make_child_with_target_date("RELEASE-1313", "Closed", "2025-01-15")
    pending = make_child_with_target_date(
        "RELEASE-1571", "Release Pending", "2025-02-28"
    )
    parent = make_parent_with_children("KONFLUX-6027", [closed, pending])

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # Should propagate the date from Release Pending child (not Closed child)
    assert len(context["updates"]) == 1
    assert "2025-02-28" in context["updates"][0]
    assert "RELEASE-1571" in context["updates"][0]


def test_target_end_date_all_done_children_excluded():
    """Test that Done and Closed children are excluded from target date calculation.

    When all children are Done/Closed and parent has an existing date, preserve it.
    """
    closed = make_child_with_target_date("RELEASE-100", "Closed", "2025-01-15")
    done = make_child_with_target_date("RELEASE-101", "Done", "2025-01-20")
    parent = make_parent_with_children("KONFLUX-1234", [closed, done])
    parent["fields"]["customfield_12345"] = "2025-01-10"  # Has existing date

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # All children are Done, so no active children - preserve the existing date
    assert len(context["updates"]) == 0
    assert len(context["comments"]) == 0


def test_target_end_date_mixed_children():
    """Test with mix of In Progress, Release Pending, and Closed children."""
    in_progress = make_child_with_target_date(
        "RELEASE-200", "In Progress", "2025-03-15"
    )
    pending = make_child_with_target_date(
        "RELEASE-201", "Release Pending", "2025-04-30"
    )
    closed = make_child_with_target_date("RELEASE-202", "Closed", "2025-01-01")
    parent = make_parent_with_children("KONFLUX-5678", [in_progress, pending, closed])

    context = {"comments": [], "updates": []}
    check_target_end_date(parent, context, dry_run=True)

    # Should use latest date from In Progress + Release Pending (exclude Closed)
    assert len(context["updates"]) == 1
    assert "2025-04-30" in context["updates"][0]
    assert "RELEASE-201" in context["updates"][0]


def test_no_children_with_target_date_preserves_date():
    """Feature with no children and a target end date should preserve the date."""
    parent = make_parent_with_children("FEAT-1", children=[], target_date="2025-06-30")
    context = {"updates": [], "comments": []}

    check_target_end_date(parent, context, dry_run=True)

    # Should return early without any updates
    assert context["updates"] == []
    assert context["comments"] == []


def test_no_children_without_target_date_continues():
    """Feature with no children and no target end date should not add updates."""
    parent = make_parent_with_children("FEAT-1", children=[], target_date=None)
    context = {"updates": [], "comments": []}

    check_target_end_date(parent, context, dry_run=True)

    # No target date to clear, no children to propagate from - no updates
    assert context["updates"] == []
    assert context["comments"] == []


def test_only_done_children_with_target_date_preserves_date():
    """Feature with only Done children and a target end date should preserve the date."""
    done_child = make_child_with_target_date("CHILD-1", "Closed", "2025-05-01")
    parent = make_parent_with_children(
        "FEAT-1", children=[done_child], target_date="2025-06-30"
    )
    context = {"updates": [], "comments": []}

    check_target_end_date(parent, context, dry_run=True)

    # Done children are filtered out, so effectively no active children
    # Should preserve the manually-set date
    assert context["updates"] == []
    assert context["comments"] == []


def test_with_active_children_updates_date():
    """Feature with active children should calculate target end date from children."""
    child = make_child_with_target_date("CHILD-1", "In Progress", "2025-07-15")
    parent = make_parent_with_children(
        "FEAT-1", children=[child], target_date="2025-06-30"
    )
    context = {"updates": [], "comments": []}

    check_target_end_date(parent, context, dry_run=True)

    # Should update to child's date since we have an active child with estimate
    assert len(context["updates"]) == 1
    assert "2025-07-15" in context["updates"][0]


def test_subtasks_are_excluded_from_target_date_calculation():
    """Sub-tasks should be excluded from target end date calculation, only Epics should be included.

    This test verifies the fix for Jira Cloud migration where sub-tasks were incorrectly
    included in children after migration. Only child Epics should influence target end dates.
    """
    epic_child = make_child_with_target_date(
        "EPIC-1", "In Progress", "2025-08-15", issuetype="Epic"
    )
    subtask_child = make_child_with_target_date(
        "SUBTASK-1", "In Progress", "2025-12-31", issuetype="Sub-task"
    )

    # Parent with both an Epic child and a Sub-task child
    parent = make_parent_with_children(
        "FEAT-1", children=[epic_child, subtask_child], target_date="2025-06-30"
    )
    context = {"updates": [], "comments": []}

    check_target_end_date(parent, context, dry_run=True)

    # Should only use Epic's date (2025-08-15), not Sub-task's date (2025-12-31)
    assert len(context["updates"]) == 1
    assert "2025-08-15" in context["updates"][0]
    assert "2025-12-31" not in context["updates"][0]
    assert "EPIC-1" in context["updates"][0]
