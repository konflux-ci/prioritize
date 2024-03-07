import mock
import pytest


class MockIssue:
    def __init__(self, idx, project, parent, rank):
        raw = {}
        raw["Context"] = {}
        raw["Context"]["Field Ids"] = {}
        raw["Context"]["Field Ids"]["Rank"] = "rank"
        raw["Context"]["Related Issues"] = {}
        raw["Context"]["Related Issues"]["Parent"] = parent

        self.key = idx
        self.idx = idx
        self.raw = raw
        self.fields = mock.MagicMock()
        self.fields.project.key = project
        self.fields.rank = rank

    def __repr__(self):
        return f"<{type(self).__name__} {self.fields.project.key}-{self.idx}>"


@pytest.fixture
def issues():
    project = "TESTPROJECT"
    parent1 = MockIssue("parent1", project, None, 1)
    child1 = MockIssue("child1", project, parent1, 2)
    parent2 = MockIssue("parent2", project, None, 3)
    child2 = MockIssue("child2", project, parent2, 4)
    parent3 = MockIssue("parent3", project, None, 5)
    child3 = MockIssue("child3", project, parent3, 6)
    return dict(child1=child1, child2=child2, child3=child3)
