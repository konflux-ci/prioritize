import datetime

import pytest


class MockComponent(dict):
    def __init__(self, name):
        self["name"] = name


class MockIssue(dict):
    def __init__(
        self,
        key,
        project,
        parent,
        rank,
        priority="Undefined",
        duedate=None,
        rice=None,
        components=None,
        labels=None,
        status=None,
        issuetype="Epic",
    ):
        self["Context"] = {}
        self["Context"]["Field Ids"] = {}
        self["Context"]["Field Ids"]["Rank"] = "rank"
        self["Context"]["Field Ids"]["Due Date"] = "duedate"
        self["Context"]["Field Ids"]["RICE Score"] = "rice"
        self["Context"]["Related Issues"] = {}
        self["Context"]["Related Issues"]["Parent"] = parent

        self["key"] = key
        self["fields"] = {}
        self["fields"]["project"] = {}
        self["fields"]["project"]["key"] = project
        self["fields"]["rank"] = rank
        self["fields"]["duedate"] = duedate
        self["fields"]["priority"] = {}
        self["fields"]["priority"]["name"] = priority
        self["fields"]["rice"] = rice
        self["fields"]["components"] = components or [] if components else []
        self["fields"]["labels"] = labels or [] if labels else []
        self["fields"]["issuetype"] = {"name": issuetype}

        # Mock status
        if status is not None:
            self["fields"]["status"] = {"statusCategory": {"name": status}}

    def __repr__(self):
        pk = self["fields"]["project"]["key"]
        r = self["fields"]["rank"]
        dd = self["fields"]["duedate"] or ""
        return f"<{type(self).__name__} {pk}-{self['key']}({r}){dd}>"


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
    child6 = MockIssue("child6", project, parent2, 8, rice=10)
    return dict(
        child1=child1,
        child2=child2,
        child3=child3,
        child4=child4,
        child5=child5,
        child6=child6,
    )


@pytest.fixture
def issues_with_priorities():
    project = "TESTPROJECT"
    child0 = MockIssue("child0", project, None, 0, priority="Blocker")
    parent1 = MockIssue("parent1", project, None, 2)
    parent2 = MockIssue("parent2", project, None, 1)
    child1 = MockIssue("child1", project, parent1, 3, priority="Undefined")
    child2 = MockIssue("child2", project, parent1, 4, priority="Blocker")
    child3 = MockIssue("child3", project, parent1, 5, priority="Trivial")
    child4 = MockIssue("child4", project, parent1, 6, priority="Major")
    child5 = MockIssue("child5", project, parent2, 7)
    child6 = MockIssue("child6", project, parent2, 8, priority="Minor")
    child7 = MockIssue("child7", project, parent2, 9)
    child8 = MockIssue("child8", project, parent2, 10)
    child9 = MockIssue("child9", project, parent2, 11)
    return dict(
        child0=child0,
        child1=child1,
        child2=child2,
        child3=child3,
        child4=child4,
        child5=child5,
        child6=child6,
        child7=child7,
        child8=child8,
        child9=child9,
    )
