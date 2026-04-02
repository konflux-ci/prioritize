"""Tests for Jira utilities (caching, preprocess helpers)."""

import dogpile.cache
import pytest

from utils.jira import preprocess


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


def test_get_parent_cache_shared_ref_one_get_issue(
    monkeypatch, memory_jira_cache
):
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
