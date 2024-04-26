"""
The reranking tries to keep the general ordering within the project.

If the issue being reranked and its parent belongs to the same project, the issue will
be reranked so as to be displayed next to the parent. E.g. all stories belonging to an
Epic will be listed after the parent Epic and before the next highest ranked Epic.

If Features from ProjectA are reranked, it will not impact the global position of
Features from ProjectB within the project.
What that means is that:
    1.  All issues related to same parent are moved as a block, keeping the ranking in
        that block. An issue without a parent is considered as a block.
    2.  When parent issues are reranked, blocks related to the parent issue's project
        are reordered. The reordering is done by swapping blocks around. Blocks can
        be swapped only if they are related to the same parent project.
Example:
    Epic1 and Epic2 are related to FeatureA from ProjectX.
    Epic3 is related to FeatureB from ProjectY.
    Epic4 does not have a parent issue.
    Epic5 is related to FeatureC from ProjectX.
    Current ranking in the project, showing blocks:
        [Epic1, Epic2], [Epic3], [Epic4], [Epic5]
    Current ranking in ProjectA:
        FeatureA, FeatureC
    If the ranking in ProjectA changes to:
        FeatureC, FeatureA
    the ranking in the project will become:
        [Epic5], [Epic3], [Epic4], [Epic1, Epic2]
    The 2 blocks for FeatureA and FeatureB have been swapped, wihtout impacting the
    ranking of the other issues.

Blocks can be moved and ranked lower if the parent status is not "In Progress".
This helps prioritize the work that is currently on-going rather than future
improvements that have been ranked very high.
"""

import jira


def check_rank(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
    favor_status: bool = False,
) -> None:
    """Rerank all issues"""
    jira_client = context["jira_client"]

    # Get blocks and current ranking
    blocks = Blocks(issues)
    old_ranking = blocks.get_issues()

    # Sort blocks and generate new ranking
    blocks.sort(favor_status=favor_status)
    new_ranking = blocks.get_issues()

    # Apply new ranking
    _set_rank(jira_client, old_ranking, new_ranking, dry_run)


def _set_rank(
    jira_client: jira.client.JIRA,
    old_ranking: list[jira.resources.Issue],
    new_ranking: list[jira.resources.Issue],
    dry_run: bool,
) -> None:
    print("\n### Reranking issues")
    previous_issue = None
    total = len(new_ranking)
    rerank = False

    for index, issue in enumerate(new_ranking):
        if issue != old_ranking[index]:
            # Once we start reranking, we don't stop.
            # This should avoid any edge case, but it's slow.
            rerank = True
        if rerank and previous_issue is not None:
            if dry_run:
                print(f"  > {issue.key} would be moved just below {previous_issue.key}")
            else:
                jira_client.rank(issue=issue.key, prev_issue=previous_issue.key)
        elif dry_run:
            print(f"  > {issue.key} is already in the right place")

        previous_issue = issue
        print(f"\r{100 * (index + 1) // total}%", end="", flush=True)


class Block:
    """A block groups a parent and all its children issues"""

    def __init__(self, parent):
        self.parent_issue = parent
        self.issues = []

    def parent_is_inprogress(self):
        if self.parent_issue is None:
            return False
        return self.parent_issue.fields.status.statusCategory.name == "In Progress"

    def __str__(self) -> str:
        p_key = self.parent_issue.key if self.parent_issue else None
        i_keys = [i.key for i in self.issues]
        return f"{p_key}: {', '.join(i_keys)}"


class Blocks(list):
    def __init__(self, issues: list[jira.resources.Issue]) -> None:
        self.blocks = []
        for issue in issues:
            self.add_issue(issue)

    def add_issue(self, issue: jira.resources.Issue) -> None:
        """Add an issue to the right block"""
        block = None
        parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
        if parent_issue is None:
            block = Block(None)
            self.blocks.append(block)
        else:
            addBlock = True
            for block in self.blocks:
                if block.parent_issue == parent_issue:
                    addBlock = False
                    break
            if addBlock:
                block = Block(parent_issue)
                self.blocks.append(block)
        block.issues.append(issue)

    def get_issues(self) -> list[jira.resources.Issue]:
        """Return a flat list of issues, in the order of appearance in the blocks"""
        issues = []
        for block in self.blocks:
            if (
                block.parent_issue is not None
                and block.parent_issue.fields.project.key
                == block.issues[0].fields.project.key
            ):
                issues.append(block.parent_issue)
            for issue in block.issues:
                issues.append(issue)
        return issues

    def sort(self, favor_status=False):
        self._sort_by_project_rank()
        if favor_status:
            self._sort_by_status()

    def _sort_by_project_rank(self):
        """Rerank blocks based on the block's project rank.
        Blocks are switch around, but a block can only be switched
        with a block of the same parent project.
        """
        if not self.blocks:
            return
        rank_field_id = self.blocks[0].issues[0].raw["Context"]["Field Ids"]["Rank"]

        # For each project, generate a ranked list of issues
        per_project_ranking = {None: []}
        for block in self.blocks:
            parent_issue = block.parent_issue
            if parent_issue is None:
                per_project_ranking[None].append(block)
                continue

            project_key = parent_issue.fields.project.key
            project_ranking = per_project_ranking.get(project_key, [])

            block_rank = getattr(parent_issue.fields, rank_field_id)
            for index, i_block in enumerate(project_ranking):
                if block_rank < getattr(i_block.parent_issue.fields, rank_field_id):
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
