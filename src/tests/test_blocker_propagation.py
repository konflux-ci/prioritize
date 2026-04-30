"""
Jira Cloud GET response semantics for Blocks links viewed from issue X:
    inwardIssue: Y  → X "is blocked by" Y  (Y is the blocker)
    outwardIssue: Y → X "blocks" Y          (Y is NOT a blocker of X)
"""

import unittest.mock as mock

import rules.team.blocker_propagation as bp
from utils.jira import get_descendant_issues


def _issue(
    key: str,
    issuetype: str,
    *,
    issuelinks: list | None = None,
    parent_key: str | None = None,
    resolution: str | None = None,
) -> dict:
    fields: dict = {"issuetype": {"name": issuetype}, "issuelinks": issuelinks or []}
    if parent_key is not None:
        fields["parent"] = {"key": parent_key}
    fields["resolution"] = {"name": resolution} if resolution else None
    return {"key": key, "fields": fields}


def _blocked_by_link(
    my_key: str, blocker: str, link_id: str = "10001", *, resolved: bool = False
) -> dict:
    """Simulate Jira Cloud GET: ``my_key`` is blocked by ``blocker``."""
    category = "Done" if resolved else "In Progress"
    return {
        "id": link_id,
        "type": {"name": "Blocks"},
        "inwardIssue": {
            "key": blocker,
            "fields": {
                "status": {"name": category, "statusCategory": {"name": category}}
            },
        },
    }


def test_blocking_issue_keys_detects_blocker():
    story = _issue(
        "KFLUXDP-10",
        "Story",
        issuelinks=[_blocked_by_link("KFLUXDP-10", "KFLUXDP-99")],
    )
    assert bp._blocking_issue_keys(story) == ["KFLUXDP-99"]


def test_blocking_issue_keys_outward_means_current_blocks_not_blocked():
    """outwardIssue: Y means current blocks Y — not a blocker of current."""
    link = {
        "id": "1",
        "type": {"name": "Blocks"},
        "outwardIssue": {"key": "KFLUXDP-99"},
    }
    story = _issue("KFLUXDP-10", "Story", issuelinks=[link])
    assert bp._blocking_issue_keys(story) == []


def test_blocking_issue_keys_ignores_inward_self_reference():
    """If inwardIssue is somehow the issue itself, skip it."""
    link = {
        "id": "1",
        "type": {"name": "Blocks"},
        "inwardIssue": {"key": "KFLUXDP-10"},
    }
    story = _issue("KFLUXDP-10", "Story", issuelinks=[link])
    assert bp._blocking_issue_keys(story) == []


def test_blocking_issue_keys_detects_by_inward_label_not_name():
    """Custom link types may omit name 'Blocks' but keep inward 'is blocked by'."""
    link = {
        "id": "1",
        "type": {
            "name": "CustomDependency",
            "inward": "is blocked by",
            "outward": "blocks",
        },
        "inwardIssue": {"key": "KFLUXDP-99"},
    }
    story = _issue("KFLUXDP-10", "Story", issuelinks=[link])
    assert bp._blocking_issue_keys(story) == ["KFLUXDP-99"]


def test_inward_blocks_entries_with_ids():
    epic = _issue(
        "KFLUXDP-30",
        "Epic",
        issuelinks=[
            _blocked_by_link("KFLUXDP-30", "KFLUXDP-99", "1"),
            _blocked_by_link("KFLUXDP-30", "KFLUXDP-98", "2"),
        ],
    )
    entries = bp._inward_blocks_entries(epic)
    assert set(entries) == {("KFLUXDP-99", "1"), ("KFLUXDP-98", "2")}


def test_blocking_issue_keys_skips_resolved_blockers():
    """Resolved blockers (statusCategory == Done) should not be propagated."""
    open_link = _blocked_by_link("X-1", "OPEN-1")
    closed_link = _blocked_by_link("X-1", "CLOSED-1", resolved=True)
    issue = _issue("X-1", "Story", issuelinks=[open_link, closed_link])
    assert bp._blocking_issue_keys(issue) == ["OPEN-1"]


def test_blocking_issue_keys_no_status_field_treated_as_open():
    """If the linked issue stub has no status data, treat it as open (safe default)."""
    link_no_status = {
        "id": "1",
        "type": {"name": "Blocks"},
        "inwardIssue": {"key": "NO-STATUS"},
    }
    issue = _issue("X-1", "Story", issuelinks=[link_no_status])
    assert bp._blocking_issue_keys(issue) == ["NO-STATUS"]


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_skips_resolved_blockers(mock_desc, _mock_batch):
    """Resolved blockers on descendants should not propagate to the parent."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    child = _issue(
        "KFLUXDP-11",
        "Story",
        issuelinks=[
            _blocked_by_link("KFLUXDP-11", "OPEN-1"),
            _blocked_by_link("KFLUXDP-11", "CLOSED-1", resolved=True),
        ],
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    calls = jira_client.create_issue_link.call_args_list
    assert len(calls) == 1
    payload = calls[0][0][0]
    assert payload["inwardIssue"]["key"] == "OPEN-1"


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_adds_missing_blockers(mock_desc, _mock_batch):
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    s1 = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")]
    )
    s2 = _issue(
        "KFLUXDP-12", "Story", issuelinks=[_blocked_by_link("KFLUXDP-12", "B2")]
    )
    mock_desc.return_value = [s1, s2]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    calls = jira_client.create_issue_link.call_args_list
    assert len(calls) == 2
    payloads = [c[0][0] for c in calls]
    # Jira Cloud create: inwardIssue=blocker, outwardIssue=blocked party (epic)
    assert {
        frozenset(
            (("inward", p["inwardIssue"]["key"]), ("outward", p["outwardIssue"]["key"]))
        )
        for p in payloads
    } == {
        frozenset((("inward", "B1"), ("outward", "KFLUXDP-30"))),
        frozenset((("inward", "B2"), ("outward", "KFLUXDP-30"))),
    }
    jira_client.remove_issue_link.assert_not_called()
    assert all("[created]" in u for u in context["updates"])


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_removes_stale_blockers(mock_desc, _mock_batch):
    epic = _issue(
        "KFLUXDP-30",
        "Epic",
        issuelinks=[
            _blocked_by_link("KFLUXDP-30", "OLD", "50"),
            _blocked_by_link("KFLUXDP-30", "KEEP", "51"),
        ],
    )
    s1 = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "KEEP")]
    )
    mock_desc.return_value = [s1]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    jira_client.remove_issue_link.assert_called_once_with("50")
    jira_client.create_issue_link.assert_not_called()
    assert any("[removed]" in u for u in context["updates"])


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_skips_non_container(mock_desc, _mock_batch):
    story = _issue("KFLUXDP-10", "Story", issuelinks=[])
    mock_desc.return_value = []

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(story, context, dry_run=False)

    mock_desc.assert_not_called()
    jira_client.create_issue_link.assert_not_called()


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_skips_when_no_descendants(mock_desc, _mock_batch):
    epic = _issue(
        "KFLUXDP-30", "Epic", issuelinks=[_blocked_by_link("KFLUXDP-30", "X")]
    )
    mock_desc.return_value = []

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    jira_client.create_issue_link.assert_not_called()
    jira_client.remove_issue_link.assert_not_called()


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_dry_run(mock_desc, _mock_batch):
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    mock_desc.return_value = [
        _issue("KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")])
    ]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=True)

    jira_client.create_issue_link.assert_not_called()
    assert context["updates"] and "dry-run" in context["updates"][0]


def test_blocking_issue_keys_handles_null_issuelinks():
    """issuelinks field can be None or absent; should return empty list."""
    issue_none = {"key": "X-1", "fields": {"issuelinks": None}}
    assert bp._blocking_issue_keys(issue_none) == []

    issue_missing = {"key": "X-2", "fields": {}}
    assert bp._blocking_issue_keys(issue_missing) == []


def test_is_blocked_by_link_type_edge_cases():
    assert bp._is_blocked_by_link_type(None) is False
    assert bp._is_blocked_by_link_type({}) is False
    assert bp._is_blocked_by_link_type({"name": "Blockers"}) is True
    assert bp._is_blocked_by_link_type({"name": "Relates"}) is False


def test_blocking_issue_keys_skips_non_blocks_link_types():
    """Non-Blocks links (e.g. Cloners, Relates) should be skipped via continue."""
    relates_link = {
        "id": "99",
        "type": {"name": "Relates"},
        "inwardIssue": {"key": "NOISE-1"},
    }
    blocks_link = _blocked_by_link("X-1", "REAL-1")
    issue = _issue("X-1", "Story", issuelinks=[relates_link, blocks_link])
    assert bp._blocking_issue_keys(issue) == ["REAL-1"]


def test_inward_blocks_entries_skips_non_blocks_and_missing_id():
    """Non-Blocks links hit continue; links without id are skipped."""
    relates_link = {
        "id": "99",
        "type": {"name": "Relates"},
        "inwardIssue": {"key": "NOISE-1"},
    }
    no_id_link = {
        "type": {"name": "Blocks"},
        "inwardIssue": {"key": "NO-ID"},
    }
    good_link = _blocked_by_link("X-1", "OK-1", "42")
    issue = _issue("X-1", "Epic", issuelinks=[relates_link, no_id_link, good_link])
    assert bp._inward_blocks_entries(issue) == [("OK-1", "42")]


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_works_on_feature(mock_desc, _mock_batch):
    """Feature is a valid container type, not just Epic."""
    feature = _issue("KONFLUX-100", "Feature", issuelinks=[])
    child = _issue(
        "KONFLUX-200", "Epic", issuelinks=[_blocked_by_link("KONFLUX-200", "EXT-1")]
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(feature, context, dry_run=False)

    calls = jira_client.create_issue_link.call_args_list
    assert len(calls) == 1
    payload = calls[0][0][0]
    assert payload["inwardIssue"]["key"] == "EXT-1"
    assert payload["outwardIssue"]["key"] == "KONFLUX-100"


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_deduplicates_same_blocker_across_children(mock_desc, _mock_batch):
    """Two children blocked by the same issue should produce one link on the Epic."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    s1 = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")]
    )
    s2 = _issue(
        "KFLUXDP-12", "Story", issuelinks=[_blocked_by_link("KFLUXDP-12", "B1")]
    )
    mock_desc.return_value = [s1, s2]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    assert jira_client.create_issue_link.call_count == 1


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_skips_self_blocker(mock_desc, _mock_batch):
    """If a descendant is 'blocked by' the Epic itself, don't create a self-link."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    child = _issue(
        "KFLUXDP-11",
        "Story",
        issuelinks=[_blocked_by_link("KFLUXDP-11", "KFLUXDP-30")],
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    jira_client.create_issue_link.assert_not_called()


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_mixed_add_and_remove(mock_desc, _mock_batch):
    """Simultaneously adds new blockers and removes stale ones."""
    epic = _issue(
        "KFLUXDP-30",
        "Epic",
        issuelinks=[_blocked_by_link("KFLUXDP-30", "OLD", "50")],
    )
    child = _issue(
        "KFLUXDP-11",
        "Story",
        issuelinks=[_blocked_by_link("KFLUXDP-11", "NEW")],
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    jira_client.remove_issue_link.assert_called_once_with("50")
    assert jira_client.create_issue_link.call_count == 1
    payload = jira_client.create_issue_link.call_args[0][0]
    assert payload["inwardIssue"]["key"] == "NEW"


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_dry_run_skips_removal_too(mock_desc, _mock_batch):
    """Dry run must not remove links either."""
    epic = _issue(
        "KFLUXDP-30",
        "Epic",
        issuelinks=[_blocked_by_link("KFLUXDP-30", "STALE", "50")],
    )
    mock_desc.return_value = [_issue("KFLUXDP-11", "Story", issuelinks=[])]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=True)

    jira_client.remove_issue_link.assert_not_called()
    jira_client.create_issue_link.assert_not_called()
    assert any("dry-run" in u for u in context["updates"])


@mock.patch.dict("os.environ", {"PRIORITIZE_BLOCKER_DIAG": "1"})
@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_diag_no_descendants_message(mock_desc, _mock_batch):
    """PRIORITIZE_BLOCKER_DIAG logs a message when descendants list is empty."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    mock_desc.return_value = []

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=True)

    assert any("0 descendants" in u for u in context["updates"])


@mock.patch.dict("os.environ", {"PRIORITIZE_BLOCKER_DIAG": "1"})
@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_diag_nothing_to_change(mock_desc, _mock_batch):
    """PRIORITIZE_BLOCKER_DIAG logs when blockers already match."""
    epic = _issue(
        "KFLUXDP-30", "Epic", issuelinks=[_blocked_by_link("KFLUXDP-30", "B1", "50")]
    )
    child = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")]
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=True)

    assert any("nothing to change" in u for u in context["updates"])


@mock.patch.dict("os.environ", {"PRIORITIZE_BLOCKER_DIAG": "2"})
@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_diag_level2_debug_output(mock_desc, _mock_batch):
    """PRIORITIZE_BLOCKER_DIAG=2 emits detailed debug info."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    child = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")]
    )
    mock_desc.return_value = [child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=True)

    debug_msgs = [u for u in context["updates"] if "DEBUG" in u]
    assert len(debug_msgs) == 1
    assert "descendant_keys" in debug_msgs[0]
    assert "to_add" in debug_msgs[0]


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_ignores_resolved_children(mock_desc, _mock_batch):
    """Resolved children's blockers should not propagate to the parent."""
    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    _issue(
        "KFLUXDP-11",
        "Story",
        issuelinks=[_blocked_by_link("KFLUXDP-11", "B1")],
        resolution="Done",
    )
    open_child = _issue(
        "KFLUXDP-12",
        "Story",
        issuelinks=[_blocked_by_link("KFLUXDP-12", "B2")],
    )
    mock_desc.return_value = [open_child]

    jira_client = mock.Mock()
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    mock_desc.assert_called_once_with(jira_client, "KFLUXDP-30", unresolved_only=True)
    calls = jira_client.create_issue_link.call_args_list
    assert len(calls) == 1
    payload = calls[0][0][0]
    assert payload["inwardIssue"]["key"] == "B2"
    assert payload["outwardIssue"]["key"] == "KFLUXDP-30"


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_create_link_permission_error_continues(mock_desc, _mock_batch):
    """Permission error on create_issue_link should log warning, not crash."""
    from requests.exceptions import HTTPError

    epic = _issue("KFLUXDP-30", "Epic", issuelinks=[])
    s1 = _issue(
        "KFLUXDP-11", "Story", issuelinks=[_blocked_by_link("KFLUXDP-11", "EXT-1")]
    )
    s2 = _issue(
        "KFLUXDP-12", "Story", issuelinks=[_blocked_by_link("KFLUXDP-12", "EXT-2")]
    )
    mock_desc.return_value = [s1, s2]

    resp = mock.Mock()
    resp.status_code = 403
    jira_client = mock.Mock()
    jira_client.create_issue_link.side_effect = [
        HTTPError("No Link Issue Permission for issue 'EXT-1'", response=resp),
        None,
    ]
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    assert jira_client.create_issue_link.call_count == 2
    assert any(
        "error" in u.lower() or "failed" in u.lower() for u in context["updates"]
    )
    assert any("[created]" in u for u in context["updates"])


@mock.patch("rules.team.blocker_propagation._batch_merge_issuelinks")
@mock.patch("rules.team.blocker_propagation.get_descendant_issues")
def test_sync_remove_link_permission_error_continues(mock_desc, _mock_batch):
    """Permission error on remove_issue_link should log warning, not crash."""
    from requests.exceptions import HTTPError

    epic = _issue(
        "KFLUXDP-30",
        "Epic",
        issuelinks=[
            _blocked_by_link("KFLUXDP-30", "STALE-1", "50"),
            _blocked_by_link("KFLUXDP-30", "STALE-2", "51"),
        ],
    )
    mock_desc.return_value = [_issue("KFLUXDP-11", "Story", issuelinks=[])]

    resp = mock.Mock()
    resp.status_code = 403
    jira_client = mock.Mock()
    jira_client.remove_issue_link.side_effect = [
        HTTPError("No Link Issue Permission", response=resp),
        None,
    ]
    context = {"jira_client": jira_client, "updates": []}
    bp.sync_blocker_links_from_descendants(epic, context, dry_run=False)

    assert jira_client.remove_issue_link.call_count == 2
    assert any(
        "error" in u.lower() or "failed" in u.lower() for u in context["updates"]
    )
    assert any("[removed]" in u for u in context["updates"])


def _child(key, resolution=None):
    fields = {"resolution": {"name": resolution} if resolution else None}
    return {"key": key, "fields": fields}


def _mock_children(tree):
    """Build a side_effect for get_children from a dict {parent_key: [child, ...]}."""

    def _side_effect(jira_client, stub, order_by=""):
        return iter(tree.get(stub["key"], []))

    return _side_effect


@mock.patch("utils.jira.get_children")
def test_descendant_bfs_single_level(mock_gc):
    mock_gc.side_effect = _mock_children(
        {"ROOT": [_child("A"), _child("B")], "A": [], "B": []}
    )
    result = get_descendant_issues(mock.Mock(), "ROOT")
    assert [c["key"] for c in result] == ["A", "B"]


@mock.patch("utils.jira.get_children")
def test_descendant_bfs_multi_level(mock_gc):
    mock_gc.side_effect = _mock_children(
        {
            "ROOT": [_child("A")],
            "A": [_child("B"), _child("C")],
            "B": [_child("D")],
            "C": [],
            "D": [],
        }
    )
    result = get_descendant_issues(mock.Mock(), "ROOT")
    assert [c["key"] for c in result] == ["A", "B", "C", "D"]


@mock.patch("utils.jira.get_children")
def test_descendant_cycle_protection(mock_gc):
    """A child pointing back to an ancestor should not cause infinite recursion."""
    mock_gc.side_effect = _mock_children(
        {
            "ROOT": [_child("A")],
            "A": [_child("B")],
            "B": [_child("ROOT"), _child("A")],
        }
    )
    result = get_descendant_issues(mock.Mock(), "ROOT")
    assert [c["key"] for c in result] == ["A", "B"]


@mock.patch("utils.jira.get_children")
def test_descendant_unresolved_only_filters_resolved(mock_gc):
    mock_gc.side_effect = _mock_children(
        {
            "ROOT": [_child("OPEN"), _child("DONE", resolution="Done")],
            "OPEN": [_child("DEEP")],
            "DEEP": [],
        }
    )
    result = get_descendant_issues(mock.Mock(), "ROOT", unresolved_only=True)
    keys = [c["key"] for c in result]
    assert "OPEN" in keys
    assert "DEEP" in keys
    assert "DONE" not in keys


@mock.patch("utils.jira.get_children")
def test_descendant_unresolved_only_skips_subtree(mock_gc):
    """Resolved node's children should not be traversed."""
    subtree_visited = []

    def _side_effect(jira_client, stub, order_by=""):
        subtree_visited.append(stub["key"])
        tree = {
            "ROOT": [_child("CLOSED", resolution="Done")],
            "CLOSED": [_child("HIDDEN")],
            "HIDDEN": [],
        }
        return iter(tree.get(stub["key"], []))

    mock_gc.side_effect = _side_effect
    result = get_descendant_issues(mock.Mock(), "ROOT", unresolved_only=True)
    assert [c["key"] for c in result] == []
    assert "CLOSED" not in subtree_visited, "Should not traverse into resolved node"


@mock.patch("utils.jira.get_children")
def test_descendant_no_children(mock_gc):
    mock_gc.side_effect = _mock_children({"ROOT": []})
    result = get_descendant_issues(mock.Mock(), "ROOT")
    assert result == []


@mock.patch("utils.jira.get_children")
def test_descendant_root_excluded_from_results(mock_gc):
    mock_gc.side_effect = _mock_children({"ROOT": [_child("A")], "A": []})
    result = get_descendant_issues(mock.Mock(), "ROOT")
    assert all(c["key"] != "ROOT" for c in result)


def test_batch_merge_populates_issuelinks():
    """Batch fetch should write issuelinks into each issue's fields."""
    link_a = _blocked_by_link("A", "B1")
    link_b = _blocked_by_link("B", "B2")
    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = {
        "issues": [
            {"key": "A", "fields": {"issuelinks": [link_a]}},
            {"key": "B", "fields": {"issuelinks": [link_b]}},
        ],
        "nextPageToken": None,
    }

    issue_a: dict = {"key": "A", "fields": {}}
    issue_b: dict = {"key": "B", "fields": {}}
    bp._batch_merge_issuelinks(jira_client, [issue_a, issue_b])

    assert issue_a["fields"]["issuelinks"] == [link_a]
    assert issue_b["fields"]["issuelinks"] == [link_b]
    assert jira_client.enhanced_jql.call_count == 1


def test_batch_merge_handles_pagination():
    """Multiple pages should all be processed."""
    link_a = _blocked_by_link("A", "B1")
    link_b = _blocked_by_link("B", "B2")
    jira_client = mock.Mock()
    jira_client.enhanced_jql.side_effect = [
        {
            "issues": [{"key": "A", "fields": {"issuelinks": [link_a]}}],
            "nextPageToken": "page2",
        },
        {
            "issues": [{"key": "B", "fields": {"issuelinks": [link_b]}}],
            "nextPageToken": None,
        },
    ]

    issue_a: dict = {"key": "A", "fields": {}}
    issue_b: dict = {"key": "B", "fields": {}}
    bp._batch_merge_issuelinks(jira_client, [issue_a, issue_b])

    assert issue_a["fields"]["issuelinks"] == [link_a]
    assert issue_b["fields"]["issuelinks"] == [link_b]
    assert jira_client.enhanced_jql.call_count == 2


def test_batch_merge_empty_list():
    """Empty input should not call the API."""
    jira_client = mock.Mock()
    bp._batch_merge_issuelinks(jira_client, [])
    jira_client.enhanced_jql.assert_not_called()


def test_batch_merge_none_response():
    """None response from enhanced_jql should be handled gracefully."""
    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = None

    issue: dict = {"key": "A", "fields": {"issuelinks": [{"old": True}]}}
    bp._batch_merge_issuelinks(jira_client, [issue])

    assert issue["fields"]["issuelinks"] == [{"old": True}]


def test_batch_merge_splits_large_batches():
    """More than _BATCH_SIZE issues should produce multiple JQL queries."""
    issues = [{"key": f"K-{i}", "fields": {}} for i in range(bp._BATCH_SIZE + 10)]
    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = {"issues": [], "nextPageToken": None}

    bp._batch_merge_issuelinks(jira_client, issues)

    assert jira_client.enhanced_jql.call_count == 2
    first_jql = jira_client.enhanced_jql.call_args_list[0][0][0]
    assert first_jql.startswith("key in (")


def test_batch_merge_null_issuelinks_stored_as_empty():
    """issuelinks: null in the response should be stored as []."""
    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = {
        "issues": [{"key": "A", "fields": {"issuelinks": None}}],
        "nextPageToken": None,
    }

    issue: dict = {"key": "A", "fields": {}}
    bp._batch_merge_issuelinks(jira_client, [issue])

    assert issue["fields"]["issuelinks"] == []
