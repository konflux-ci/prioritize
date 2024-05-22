"""
The reranking here works much the same as in the basic rank check,
except here issues with an upcoming duedate are sorted into a
special "timesensitive" block that is ranked to the top of the list.
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

    print(''.join(list(difflib.unified_diff(
        [f"{issue.key} {issue.fields.summary}\n" for issue in old_ranking],
        [f"{issue.key} {issue.fields.summary}\n" for issue in new_ranking],
        "old_ranking",
        "new_ranking",
    ))))

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
    """A block groups a parent and all its children issues"""

    def __init__(self, parent):
        self.parent_issue = parent
        self.issues = []

    def yield_issues(self):
        yield from self.issues

    def parent_is_inprogress(self):
        if self.parent_issue is None:
            return False
        return self.parent_issue.fields.status.statusCategory.name == "In Progress"

    @property
    def rank(self):
        rank_field_id = self.issues[0].raw["Context"]["Field Ids"]["Rank"]
        if self.parent_issue:
            return getattr(self.parent_issue.fields, rank_field_id)

    def __str__(self) -> str:
        p_key = self.parent_issue.key if self.parent_issue else None
        i_keys = [i.key for i in self.issues]
        return f"{p_key}: {', '.join(i_keys)}"

    def claims(self, issue) -> bool:
        parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
        return self.parent_issue == parent_issue


class TimeSensitiveBlock(Block):
    """A special-case block that gets ranked to the top"""

    def yield_issues(self):
        if not self.issues:
            return
        duedate_field_id = self.issues[0].raw["Context"]["Field Ids"]["Due Date"]
        duedate = lambda issue: getattr(issue.fields, duedate_field_id)
        yield from sorted(self.issues, key=duedate)

    @property
    def rank(self):
        return float("-inf")

    def parent_is_inprogress(self):
        return False

    def claims(self, issue) -> bool:
        return self._claims(issue)

    @staticmethod
    def _claims(issue) -> bool:
        duedate_field_id = issue.raw["Context"]["Field Ids"]["Due Date"]
        critical_deadline = (
            datetime.datetime.today() + datetime.timedelta(days=30 * 3)
        ).strftime("%Y-%m-%d")
        duedate = getattr(issue.fields, duedate_field_id)
        return duedate and duedate < critical_deadline


class Blocks(list):
    def __init__(self, issues: list[jira.resources.Issue]) -> None:
        self.blocks = [TimeSensitiveBlock(None)]
        for issue in issues:
            self.add_issue(issue)

    def add_issue(self, issue: jira.resources.Issue) -> None:
        """Add an issue to the right block"""
        block = None
        addBlock = True
        parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
        for block in self.blocks:
            if block.claims(issue):
                addBlock = False
                break
        if addBlock:
            parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
            block = Block(parent_issue)
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
        self._sort_by_project_rank()
        self._sort_by_status()
        self._deprioritize_orphans()
        self._prioritize_timesensitive_block()

    def _sort_by_project_rank(self):
        """Rerank blocks based on the block's project rank.
        Blocks are switch around, but a block can only be switched
        with a block of the same parent project.
        """

        # For each project, generate a ranked list of issues
        per_project_ranking = {None: []}
        for block in self.blocks:
            parent_issue = block.parent_issue
            if parent_issue is None:
                project_key = None
            else:
                project_key = parent_issue.fields.project.key
            project_ranking = per_project_ranking.get(project_key, [])

            if block.rank is None:
                per_project_ranking[None].append(block)
                continue

            for index, i_block in enumerate(project_ranking):
                if block.rank < i_block.rank:
                    project_ranking.insert(index, block)
                    break
            if block not in project_ranking:
                project_ranking.append(block)

            per_project_ranking[project_key] = project_ranking

        # Go through all the blocks, selecting the highest issue for the
        # given project.
        ranked_blocks = []
        for block in self.blocks:
            project = None
            if block.parent_issue:
                project = block.parent_issue.fields.project.key
            ranked_blocks.append(per_project_ranking[project].pop(0))

        self.blocks = ranked_blocks

    def _sort_by_status(self):
        """Issues that are actively being worked on are more important
        than issues marked as important but for which no work is on-going."""
        inprogress = []
        new = []

        for block in self.blocks:
            if block.parent_is_inprogress():
                inprogress.append(block)
            else:
                new.append(block)

        self.blocks = inprogress + new

    def _deprioritize_orphans(self):
        """Issues with no parent are deprioritized."""
        orphans = []
        other = []

        for block in self.blocks:
            if block.parent_issue is None:
                orphans.append(block)
            else:
                other.append(block)

        self.blocks = other + orphans

    def _prioritize_timesensitive_block(self):
        """Issues that are time sensitive rise to the top of the list."""
        timesensitive = []
        other = []

        for block in self.blocks:
            if type(block) is TimeSensitiveBlock:
                timesensitive.append(block)
            else:
                other.append(block)

        self.blocks = timesensitive + other
