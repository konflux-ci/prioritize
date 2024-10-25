"""
The reranking here prioritizes items with a fixVersion, but otherwise tries to
maintain the existing ordering within a project.
"""

import datetime
import difflib

import jira


def check_fixversion_rank(
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

    def __repr__(self):
        return f"<rules.team.fixversion_rank.Block based on <None>, containing {len(self.issues)} issues>"

    def __init__(self):
        self.issues = []

    def yield_issues(self):
        yield from self.issues

    @property
    def rank(self):
        return 1

    def claims(self, issue) -> bool:
        return not FixVersionBlock._claims(issue)


class FixVersionBlock(Block):
    """A special-case block that gets ranked to the top"""

    def yield_issues(self):
        """Within the fixversion block, issues get sorted by due date"""
        duedate_field_id = self.issues[0].raw["Context"]["Field Ids"]["Due Date"]
        duedate = lambda issue: getattr(issue.fields, duedate_field_id) or "9999-99-99"
        yield from sorted(self.issues, key=duedate)

    @property
    def rank(self):
        return float("-inf")

    def claims(self, issue) -> bool:
        return self._claims(issue)

    @staticmethod
    def _earliest_fixversion_date(issue):
        fixversions = issue.fields.fixVersions
        if not fixversions:
            return None
        dates = [
            fixversion.releaseDate
            for fixversion in fixversions
            if hasattr(fixversion, "releaseDate")
        ]
        if not dates:
            return None
        return sorted(dates)[0]

    @staticmethod
    def _claims(issue) -> bool:
        critical_deadline = (
            datetime.datetime.today() + datetime.timedelta(days=30 * 3)
        ).strftime("%Y-%m-%d")
        date = FixVersionBlock._earliest_fixversion_date(issue)
        return date and date < critical_deadline


class Blocks(list):
    def __init__(self, issues: list[jira.resources.Issue]) -> None:
        self.blocks = [FixVersionBlock()]
        for issue in issues:
            self.add_issue(issue)

    def add_issue(self, issue: jira.resources.Issue) -> None:
        """Add an issue to the right block"""
        block = None
        addBlock = True
        for block in self.blocks:
            if block.claims(issue):
                addBlock = False
                break
        if addBlock:
            block = Block()
            self.blocks.append(block)
        block.issues.append(issue)

    def get_issues(self) -> list[jira.resources.Issue]:
        """Return a flat list of issues, in the order of appearance in the blocks"""
        issues = []
        for block in self.blocks:
            for issue in block.yield_issues():
                issues.append(issue)
        return issues

    def sort(self):
        self._prioritize_fixversion_block()

    def _prioritize_fixversion_block(self):
        """Issues tied to fixVersions rise to the top of the list."""
        fixversion = []
        other = []

        for block in self.blocks:
            if type(block) is FixVersionBlock:
                fixversion.append(block)
            else:
                other.append(block)

        self.blocks = fixversion + other
