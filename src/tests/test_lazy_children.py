"""Tests for lazy child issue fetching (LazyChildIssues / get_children)."""

import pytest

from utils.jira import LazyChildIssues, get_children, preprocess


def _minimal_field_ids():
    return {
        "Rank": "customfield_rank",
        "Target Start Date": "cf_ts",
        "Target End Date": "cf_te",
        "Due Date": "duedate",
        "RICE Score": "cf_rice",
        "Parent": "parent",
    }


def _child_payload(key: str):
    return {
        "key": key,
        "fields": {
            "summary": f"s-{key}",
            "status": {"statusCategory": {"name": "To Do"}},
            "issuelinks": [],
        },
    }


@pytest.fixture
def fake_jira():
    class FakeJira:
        pass

    return FakeJira()


def test_lazy_children_bool_peek_then_iter_no_duplicate_fetch(
    monkeypatch, fake_jira
):
    calls = []

    def fake_page(jira_client, query, fields, next_page_token):
        calls.append(next_page_token)
        if next_page_token is None:
            return {
                "issues": [_child_payload("C-1"), _child_payload("C-2")],
                "nextPageToken": None,
            }
        raise AssertionError("unexpected second page request")

    monkeypatch.setattr("utils.jira._enhanced_jql_page", fake_page)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    parent = {"key": "P-1", "fields": {"project": {"key": "PR"}}}
    lazy = LazyChildIssues(fake_jira, parent, "")

    assert bool(lazy) is True
    assert calls == [None]

    children = list(lazy)
    assert [c["key"] for c in children] == ["C-1", "C-2"]
    assert calls == [None]
    assert all(c["_jira_client"] is fake_jira for c in children)


def test_lazy_children_iter_sets_context(monkeypatch, fake_jira):
    def fake_page(jira_client, query, fields, next_page_token):
        if next_page_token is None:
            return {"issues": [_child_payload("C-9")], "nextPageToken": None}
        raise AssertionError("unexpected page")

    monkeypatch.setattr("utils.jira._enhanced_jql_page", fake_page)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    parent = {"key": "P-2", "fields": {}}
    lazy = LazyChildIssues(fake_jira, parent, "")
    out = list(lazy)
    assert len(out) == 1
    child = out[0]
    assert child["Context"]["Related Issues"]["Parent"] is parent
    assert child["_jira_client"] is fake_jira


def test_lazy_children_multipage_order(monkeypatch, fake_jira):
    def fake_page(jira_client, query, fields, next_page_token):
        if next_page_token is None:
            return {
                "issues": [_child_payload("A")],
                "nextPageToken": "tok2",
            }
        if next_page_token == "tok2":
            return {
                "issues": [_child_payload("B")],
                "nextPageToken": None,
            }
        raise AssertionError("bad token")

    monkeypatch.setattr("utils.jira._enhanced_jql_page", fake_page)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    lazy = LazyChildIssues(fake_jira, {"key": "P-3", "fields": {}}, "")
    assert [c["key"] for c in lazy] == ["A", "B"]


def test_lazy_children_empty(monkeypatch, fake_jira):
    def fake_page(jira_client, query, fields, next_page_token):
        return {"issues": [], "nextPageToken": None}

    monkeypatch.setattr("utils.jira._enhanced_jql_page", fake_page)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    lazy = LazyChildIssues(fake_jira, {"key": "P-0", "fields": {}}, "")
    assert not lazy
    assert list(lazy) == []


def test_lazy_children_concurrent_iter_raises(monkeypatch, fake_jira):
    def fake_page(jira_client, query, fields, next_page_token):
        return {
            "issues": [_child_payload("X"), _child_payload("Y")],
            "nextPageToken": None,
        }

    monkeypatch.setattr("utils.jira._enhanced_jql_page", fake_page)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    lazy = LazyChildIssues(fake_jira, {"key": "P-4", "fields": {}}, "")
    g1 = iter(lazy)
    next(g1)
    with pytest.raises(RuntimeError, match="concurrent"):
        iter(lazy)
    list(g1)


def test_get_children_returns_lazy(monkeypatch, fake_jira):
    monkeypatch.setattr("utils.jira._enhanced_jql_page", lambda *a, **k: None)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    parent = {"key": "P-X", "fields": {}}
    ch = get_children(fake_jira, parent)
    assert isinstance(ch, LazyChildIssues)
    assert not ch  # empty response


def test_preprocess_assigns_lazy_children(monkeypatch, fake_jira):
    monkeypatch.setattr("utils.jira._enhanced_jql_page", lambda *a, **k: None)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())
    monkeypatch.setattr("utils.jira.get_parent", lambda jc, iss: None)
    monkeypatch.setattr("utils.jira.get_blocks", lambda jc, iss: [])

    issue = {
        "key": "ROOT",
        "fields": {"issuelinks": []},
    }
    preprocess(fake_jira, [issue])
    assert isinstance(
        issue["Context"]["Related Issues"]["Children"], LazyChildIssues)


def test_failed_fetch_marks_lazy_dead(monkeypatch, fake_jira):
    def boom(*a, **k):
        raise ConnectionError("x")

    monkeypatch.setattr("utils.jira._enhanced_jql_page", boom)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    lazy = LazyChildIssues(fake_jira, {"key": "P-dead", "fields": {}}, "")
    with pytest.raises(ConnectionError):
        bool(lazy)
    with pytest.raises(RuntimeError, match="failed earlier"):
        bool(lazy)
