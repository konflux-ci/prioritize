import datetime

import mock
import pytest


class MockIssue:
    def __init__(self, idx, project, parent, rank, duedate=None):
        raw = {}
        raw["Context"] = {}
        raw["Context"]["Field Ids"] = {}
        raw["Context"]["Field Ids"]["Rank"] = "rank"
        raw["Context"]["Field Ids"]["Due Date"] = "duedate"
        raw["Context"]["Related Issues"] = {}
        raw["Context"]["Related Issues"]["Parent"] = parent

        self.key = idx
        self.idx = idx
        self.raw = raw
        self.fields = mock.MagicMock()
        self.fields.project.key = project
        self.fields.rank = rank
        self.fields.duedate = duedate

    def __repr__(self):
        return f"<{type(self).__name__} {self.fields.project.key}-{self.idx}({self.fields.rank})>"


@pytest.fixture
def issues():
    project = "TESTPROJECT"
    child0 = MockIssue("child0", project, None, 0)
    parent1 = MockIssue("parent1", project, None, 1)
    child1 = MockIssue("child1", project, parent1, 2)
    parent2 = MockIssue("parent2", project, None, 3)
    child2 = MockIssue("child2", project, parent2, 4)
    parent3 = MockIssue("parent3", project, None, 5)
    child3 = MockIssue("child3", project, parent3, 6)
    child4 = MockIssue("child4", project, None, 7)
    return dict(
        child0=child0, child1=child1, child2=child2, child3=child3, child4=child4
    )


@pytest.fixture
def issues_with_due_dates():
    project = "TESTPROJECT"
    parent1 = MockIssue("parent1", project, None, 1)
    child1 = MockIssue("child1", project, parent1, 2)
    parent2 = MockIssue("parent2", project, None, 3)
    child2 = MockIssue("child2", project, parent2, 4)
    fmt = "%Y-%m-%d"
    duedate = (datetime.datetime.today() + datetime.timedelta(days=30 * 7)).strftime(
        fmt
    )
    child3 = MockIssue("child3", project, parent2, 5, duedate=duedate)
    duedate = (datetime.datetime.today() + datetime.timedelta(days=30 * 2)).strftime(
        fmt
    )
    child4 = MockIssue("child4", project, parent2, 6, duedate=duedate)
    duedate = (datetime.datetime.today() + datetime.timedelta(days=30 * 1)).strftime(
        fmt
    )
    child5 = MockIssue("child5", project, parent2, 7, duedate=duedate)
    return dict(
        child1=child1, child2=child2, child3=child3, child4=child4, child5=child5
    )
