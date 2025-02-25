"""
The reranking here splits the backlog into three blocks:

* A first block prioritizes items with a duedate; items that are scheduled
  must come first.
* A second block leaves the existing order unchanged; we want manual control of
  priorities.
* A third block order the bottom third of the backlog by RICE score; for items
  at the tail end of the backlog, manual sorting is too much trouble. Let a
  heuristic order them so we can more conveniently pull items up into the manual
  regime.

"""

import datetime
import difflib

import jira


def check_timesensitive_rank(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
) -> None:
    """Rerank all issues"""
    jira_client = context["jira_client"]

    # Get blocks and current ranking
    blocks = Blocks(issues)
    old_ranking = issues

    # Sort blocks and generate new ranking
    blocks.sort()
    new_ranking = blocks.get_issues()

    # Apply new ranking
    _set_rank(jira_client, old_ranking, new_ranking, dry_run)


def _set_rank(
    jira_client: jira.client.JIRA,
    old_ranking: list[jira.resources.Issue],
    new_ranking: list[jira.resources.Issue],
    dry_run: bool,
) -> None:
    print(f"\n### Reranking issues ({__name__})")
    previous_issue = None
    total = len(new_ranking)
    rerank = False

    print(
        "".join(
            list(
                difflib.unified_diff(
                    [f"{issue.key} {issue.fields.summary}\n" for issue in old_ranking],
                    [f"{issue.key} {issue.fields.summary}\n" for issue in new_ranking],
                    "old_ranking",
                    "new_ranking",
                )
            )
        )
    )

    for index, issue in enumerate(new_ranking):
        if issue != old_ranking[index]:
            # Once we start reranking, we don't stop.
            # This should avoid any edge case, but it's slow.
            rerank = True
        if rerank and previous_issue is not None:
            if dry_run:
                print(f"  > {issue.key}")
            else:
                jira_client.rank(issue=issue.key, prev_issue=previous_issue.key)
        previous_issue = issue
        print(f"\r{100 * (index + 1) // total}%", end="", flush=True)


class Block:
    """A block groups issues"""

    def __init__(self):
        self.issues = []

    def __repr__(self):
        return f"<{type(self)}, containing {len(self.issues)} issues>"

    def claims(self, issue, issues) -> bool:
        raise NotImplementedError()


class InertBlock(Block):
    """An inert block doesn't modify the order of its issues"""

    def yield_issues(self):
        yield from self.issues

    def claims(self, issue, issues) -> bool:
        return not DueDateBlock._claims(issue) and not RICEBlock._claims(issue, issues)


class RICEBlock(Block):
    """A special case blocks that sorts its issues by RICE score"""

    def yield_issues(self):
        if not self.issues:
            return
        rice_field_id = self.issues[0].raw["Context"]["Field Ids"]["RICE Score"]
        rice = lambda issue: float(getattr(issue.fields, rice_field_id) or "0")
        yield from sorted(self.issues, key=rice, reverse=True)

    def claims(self, issue, issues) -> bool:
        return self._claims(issue, issues)

    @staticmethod
    def _claims(issue, issues) -> bool:
        if not issues:
            return False
        i = issues.index(issue)
        n = len(issues)
        return (i / n) > 0.66


class DueDateBlock(Block):
    """A special-case block that gets ranked to the top"""

    def yield_issues(self):
        """Within the DueDate block, issues get sorted by due date"""
        if not self.issues:
            return
        duedate_field_id = self.issues[0].raw["Context"]["Field Ids"]["Due Date"]
        duedate = lambda issue: getattr(issue.fields, duedate_field_id) or "9999-99-99"
        yield from sorted(self.issues, key=duedate)

    def claims(self, issue, issues) -> bool:
        return self._claims(issue)

    @staticmethod
    def _claims(issue) -> bool:
        critical_deadline = (
            datetime.datetime.today() + datetime.timedelta(days=30 * 4)
        ).strftime("%Y-%m-%d")
        duedate_field_id = issue.raw["Context"]["Field Ids"]["Due Date"]
        date = getattr(issue.fields, duedate_field_id)
        return date and date < critical_deadline


class Blocks(list):
    def __init__(self, issues: list[jira.resources.Issue]) -> None:
        self.blocks = [DueDateBlock(), InertBlock(), RICEBlock()]
        for issue in issues:
            self.add_issue(issue, issues)

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
