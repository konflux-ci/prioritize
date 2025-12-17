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

import celpy

from utils.cel import issue_as_cel
from utils.jira import rank_issues


def check_timesensitive_rank(
    issues: list[dict],
    context: dict,
    dry_run: bool,
    manual_override: str = None,
) -> None:
    """Rerank all issues"""

    # Get blocks and current ranking
    blocks = Blocks(issues, manual_override)
    old_ranking = issues

    # Sort blocks and generate new ranking
    blocks.sort()
    new_ranking = blocks.get_issues()

    # Apply new ranking
    rank_issues(new_ranking, old_ranking, dry_run)


class Block:
    """A block groups issues"""

    def __init__(self, manual_override: str = None):
        self.issues = []
        self.manual_override = manual_override
        if self.manual_override:
            env = celpy.Environment()
            self.program = env.program(env.compile(self.manual_override))

    def __repr__(self):
        return f"<{type(self)}, containing {len(self.issues)} issues>"

    def claims(self, issue, issues) -> bool:
        raise NotImplementedError()

    def _matches_manual_override(self, issue) -> bool:
        """Check if issue matches manual_override expression"""
        if self.manual_override:
            return self.program.evaluate(issue_as_cel(issue))
        return False


class InertBlock(Block):
    """An inert block doesn't modify the order of its issues"""

    def yield_issues(self):
        yield from self.issues

    def claims(self, issue, issues) -> bool:
        # If manual_override matches, claim the issue for manual control
        if self._matches_manual_override(issue):
            return True
        # Otherwise, claim issues that aren't in DueDateBlock or RICEBlock
        return not DueDateBlock._claims(issue) and not RICEBlock._claims(issue, issues)


class RICEBlock(Block):
    """A special case blocks that sorts its issues by RICE score"""

    def yield_issues(self):
        if not self.issues:
            return
        rice_field_id = self.issues[0]["Context"]["Field Ids"]["RICE Score"]
        rice = lambda issue: float(issue["fields"].get(rice_field_id, "0") or "0")
        yield from sorted(self.issues, key=rice, reverse=True)

    def claims(self, issue, issues) -> bool:
        # Don't claim if manual_override matches - let InertBlock handle it
        if self._matches_manual_override(issue):
            return False
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
        duedate_field_id = self.issues[0]["Context"]["Field Ids"]["Due Date"]
        duedate = lambda issue: issue["fields"][duedate_field_id] or "9999-99-99"
        yield from sorted(self.issues, key=duedate)

    def claims(self, issue, issues) -> bool:
        # Don't claim if manual_override matches - let InertBlock handle it
        if self._matches_manual_override(issue):
            return False
        return self._claims(issue)

    @staticmethod
    def _claims(issue) -> bool:
        critical_deadline = (
            datetime.datetime.today() + datetime.timedelta(days=30 * 4)
        ).strftime("%Y-%m-%d")
        duedate_field_id = issue["Context"]["Field Ids"]["Due Date"]
        date = issue["fields"][duedate_field_id]
        return date and date < critical_deadline


class Blocks(list):
    def __init__(self, issues: list[dict], manual_override: str = None) -> None:
        self.blocks = [
            DueDateBlock(manual_override),
            InertBlock(manual_override),
            RICEBlock(manual_override),
        ]
        for issue in issues:
            self.add_issue(issue, issues)

    def add_issue(self, issue: dict, issues: list[dict]) -> None:
        """Add an issue to the right block among a fixed set of blocks"""
        block = None
        for block in self.blocks:
            if block.claims(issue, issues):
                break
        else:
            raise RuntimeError(f"No block claims issue {issue}")
        block.issues.append(issue)

    def get_issues(self) -> list[dict]:
        """Return a flat list of issues, in the order of appearance in the blocks"""
        issues = []
        for block in self.blocks:
            for issue in block.yield_issues():
                issues.append(issue)
        return issues
