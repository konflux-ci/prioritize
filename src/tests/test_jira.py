"""Tests for Jira utilities (caching, preprocess helpers)."""

import unittest.mock as mock

import dogpile.cache
import pytest

import utils.jira as jira_mod
from utils.jira import get_fields_ids, preprocess, query_issues, rank_issues


def _minimal_field_ids():
    return {
        "Rank": "customfield_rank",
        "Target Start Date": "cf_ts",
        "Target End Date": "cf_te",
        "Due Date": "duedate",
        "RICE Score": "cf_rice",
        "Parent": "parent",
    }


@pytest.fixture
def memory_jira_cache(monkeypatch):
    """Use in-memory dogpile region so get_parent issue caching is testable."""
    region = dogpile.cache.make_region().configure(
        "dogpile.cache.memory",
        expiration_time=3600,
    )
    monkeypatch.setattr("utils.jira.cache", region)


@pytest.fixture(autouse=True)
def _reset_field_ids_cache():
    """Ensure the module-level cache doesn't leak between tests."""
    original = jira_mod._field_ids_cache
    jira_mod._field_ids_cache = None
    yield
    jira_mod._field_ids_cache = original


def test_get_parent_cache_shared_ref_one_get_issue(monkeypatch, memory_jira_cache):
    get_issue_calls: list[str] = []

    class FakeJira:
        def get_issue(self, key: str) -> dict:
            get_issue_calls.append(key)
            return {"key": key, "fields": {"issuelinks": []}}

    monkeypatch.setattr("utils.jira._enhanced_jql_page", lambda *a, **k: None)
    monkeypatch.setattr("utils.jira.get_fields_ids", lambda jc: _minimal_field_ids())

    jc = FakeJira()
    parent_key = "PAR-1"
    issue_a = {
        "key": "CH-A",
        "fields": {"parent": {"key": parent_key}, "issuelinks": []},
    }
    issue_b = {
        "key": "CH-B",
        "fields": {"parent": {"key": parent_key}, "issuelinks": []},
    }

    preprocess(jc, [issue_a, issue_b])

    assert get_issue_calls == [parent_key]
    pa = issue_a["Context"]["Related Issues"]["Parent"]
    pb = issue_b["Context"]["Related Issues"]["Parent"]
    assert pa is not None and pb is not None
    assert pa is pb


@mock.patch("utils.jira._search")
def test_query_issues_builds_correct_jql(mock_search):
    """query_issues should produce Cloud-compatible JQL with resolution IS EMPTY."""
    mock_search.return_value = [{"key": "P-1"}]
    result = query_issues(
        mock.Mock(), "PROJ", "filter!=999", "Epic", "rank ASC", verbose=False
    )
    jql = mock_search.call_args[0][1]
    assert "resolution IS EMPTY" in jql
    assert "issuetype=Epic" in jql
    assert "AND filter!=999" in jql
    assert jql.endswith("ORDER BY rank ASC")
    assert result == [{"key": "P-1"}]


@mock.patch("utils.jira._search")
def test_query_issues_omits_subquery_when_empty(mock_search):
    mock_search.return_value = [{"key": "P-1"}]
    query_issues(mock.Mock(), "PROJ", "", "Story", "rank ASC", verbose=False)
    jql = mock_search.call_args[0][1]
    assert "project=PROJ AND resolution IS EMPTY AND issuetype=Story" in jql
    assert jql.count("AND") == 2


@mock.patch("utils.jira._search")
def test_query_issues_omits_order_when_empty(mock_search):
    mock_search.return_value = [{"key": "P-1"}]
    query_issues(mock.Mock(), "PROJ", "", "Epic", "", verbose=False)
    jql = mock_search.call_args[0][1]
    assert "ORDER BY" not in jql


def test_search_prints_hint_on_empty_results(monkeypatch, memory_jira_cache, capsys):
    """When verbose search returns 0 results, the diagnostic hint should print."""
    monkeypatch.setattr("utils.jira._jql_fields_list", lambda jc: ["summary"])

    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = {
        "issues": [],
        "nextPageToken": None,
    }

    from utils.jira import _search

    _search(jira_client, "project=X AND issuetype=Epic", verbose=True)
    captured = capsys.readouterr().out
    assert "If unexpected" in captured
    assert "0 results" in captured


def test_search_no_hint_when_results_found(monkeypatch, memory_jira_cache, capsys):
    monkeypatch.setattr("utils.jira._jql_fields_list", lambda jc: ["summary"])

    jira_client = mock.Mock()
    jira_client.enhanced_jql.return_value = {
        "issues": [{"key": "X-1"}],
        "nextPageToken": None,
    }

    from utils.jira import _search

    _search(jira_client, "project=X AND issuetype=Epic WITH_RESULTS", verbose=True)
    captured = capsys.readouterr().out
    assert "1 results" in captured
    assert "If unexpected" not in captured


def test_get_fields_ids_returns_cache_on_second_call():
    """Second call should hit _field_ids_cache and skip the API entirely."""
    fake_fields = [
        {"name": "Rank", "id": "cf_rank"},
        {"name": "Target start", "id": "cf_ts"},
        {"name": "Target end", "id": "cf_te"},
        {"name": "Due date", "id": "cf_due"},
        {"name": "RICE Score", "id": "cf_rice"},
        {"name": "Parent", "id": "cf_parent"},
    ]

    jira_client = mock.Mock()
    jira_client.get_all_fields.return_value = fake_fields

    first = get_fields_ids(jira_client)
    assert jira_client.get_all_fields.call_count == 1

    second = get_fields_ids(jira_client)
    assert jira_client.get_all_fields.call_count == 1
    assert first is second


def test_rank_issues_returns_early_on_empty_new_ranking():
    rank_issues([], [{"_jira_client": mock.Mock()}], dry_run=False)


def test_rank_issues_returns_early_on_empty_old_ranking():
    rank_issues([{"_jira_client": mock.Mock()}], [], dry_run=False)


def test_rank_issues_returns_early_on_both_empty():
    rank_issues([], [], dry_run=False)
