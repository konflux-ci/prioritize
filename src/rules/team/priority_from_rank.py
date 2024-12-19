"""
Set priority on issues based on the feature rank.

Highly ranked features are critical, the lowest ranked features are minor

"""

import jira

from utils.jira import update


def check_priority_from_rank(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
) -> None:
    """Set priority based on rank"""
    jira_client = context["jira_client"]
    footer = context["footer"]

    # Get blocks and current ranking
    blocks = Blocks(issues)

    # Apply new ranking
    total = blocks.size()
    for block in blocks:
        priority = block.get_priority()
        for issue in block.yield_issues():
            rank = blocks.rank(issue)
            _set_priority(jira_client, issue, priority, rank, total, footer, dry_run)


def _set_priority(
    jira_client: jira.client.JIRA,
    issue: jira.resources.Issue,
    priority: str,
    rank: int,
    total: int,
    footer: str,
    dry_run: bool,
) -> None:

    if issue.fields.priority.name == priority:
        return

    message = (
        f"Updating priority from {issue.fields.priority} to {priority} to reflect "
        f"{issue.key}'s current rank in the unified backlog (position {rank + 1} "
        f"of {total})"
    )
    print(message)
    if not dry_run:
        update(issue, {"priority": {"name": priority}})
        if footer:
            message = f"{message}\n\n{footer}"
        jira_client.add_comment(issue.key, message)


class Block:
    """A block groups issues"""

    def __init__(self, priority, threshold):
        self.issues = []
        self.priority = priority
        self.threshold = threshold

    def __repr__(self):
        return f"<{type(self)}: priority: {self.priority}>"

    def yield_issues(self):
        yield from self.issues

    def get_priority(self):
        return self.priority

    def claims(self, issue, issues) -> bool:
        if not issues:
            return False
        i = issues.index(issue)
        n = len(issues)
        return (i / n) <= self.threshold


class Blocks(object):
    def __init__(self, issues: list[jira.resources.Issue]) -> None:
        self.issues = issues
        self.blocks = [
            Block(priority="Critical", threshold=0.0625),
            Block(priority="Major", threshold=0.125),
            Block(priority="Normal", threshold=0.25),
            Block(priority="Minor", threshold=1),
            # No blockers.
            # Block(priority="Blocker", threshold=1),
        ]
        for issue in issues:
            self.add_issue(issue, issues)

    def __iter__(self):
        yield from self.blocks

    def rank(self, issue):
        return self.issues.index(issue)

    def size(self):
        return len(self.issues)

    def add_issue(
        self, issue: jira.resources.Issue, issues: list[jira.resources.Issue]
    ) -> None:
        """Add an issue to the right block among a fixed set of blocks"""
        block = None
        for block in self.blocks:
            if block.claims(issue, issues):
                break
        else:
            raise RuntimeError(f"No block claims issue {issue}")
        block.issues.append(issue)

    def get_issues(self) -> list[jira.resources.Issue]:
        """Return a flat list of issues, in the order of appearance in the blocks"""
        issues = []
        for block in self.blocks:
            for issue in block.yield_issues():
                issues.append(issue)
        return issues
