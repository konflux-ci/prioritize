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
"""
import jira


def check_rank(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
) -> None:
    """Rerank all issues"""

    current_project_ranking, per_project_ranking = _get_ranking_data(issues)

    rank_field_id = issues[0].raw["Context"]["Field Ids"]["Rank"]
    _sort_parents_by_rank_per_project(per_project_ranking, rank_field_id)

    # Assign rank to issues
    if not dry_run:
        jira_client = context["jira_client"]
        _set_rank(jira_client, issues, current_project_ranking, per_project_ranking)


def _get_ranking_data(issues: list[jira.resources.Issue]) -> tuple:
    # Ranks of the "blocks" (c.f. doc in the file header)
    current_project_ranking = []

    # Issues are stored from highest ranked to lowest ranked
    per_project_ranking = {None: []}

    for issue in issues:
        parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]

        # Issues without parent are stored in the "None" project
        if parent_issue is None:
            parent_issue_project = None
            current_project_ranking.append(parent_issue_project)
            per_project_ranking[parent_issue_project].append([issue])
            continue

        # Issues with a parent are stored with their parent project
        parent_issue_project = parent_issue.fields.project.key
        if parent_issue_project not in per_project_ranking.keys():
            per_project_ranking[parent_issue_project] = []
        if parent_issue not in per_project_ranking[parent_issue_project]:
            current_project_ranking.append(parent_issue_project)
            per_project_ranking[parent_issue_project].append(parent_issue)

    return current_project_ranking, per_project_ranking


def _sort_parents_by_rank_per_project(
    per_project_ranking: dict, rank_field_id: str
) -> None:
    """Sort parents by rank on a per project basis

    The "None" project is already sorted.
    """
    for project, issues in per_project_ranking.items():
        if project is not None:
            per_project_ranking[project] = sorted(
                issues, key=lambda x: getattr(x.fields, rank_field_id)
            )


def _set_rank(
    jira_client: jira.client.JIRA,
    issues: list[jira.resources.Issue],
    current_project_ranking: list,
    per_project_ranking: dict[str, list],
) -> None:
    print("\n### Reranking issues")
    previous_issue = None
    total = len(issues)
    count = 0

    # Process "blocks"
    for project in current_project_ranking:
        if project is None:
            issues_related_to_parent = per_project_ranking[None].pop(0)
        else:
            parent_issue = per_project_ranking[project].pop(0)
            issues_related_to_parent = [
                i
                for i in issues
                if i.raw["Context"]["Related Issues"]["Parent"] == parent_issue
            ]

            # Ensure that children are right after their parent when they belong to the
            # same project
            if (
                parent_issue.fields.project.key
                == issues_related_to_parent[0].fields.project.key
            ):
                previous_issue = parent_issue

        # Rerank issues from the 'block'
        for issue in issues_related_to_parent:
            count += 1
            if previous_issue is not None:
                jira_client.rank(issue=issue.key, prev_issue=previous_issue.key)
                print(f"\r{100*count//total}%", end="", flush=True)
            previous_issue = issue
    print()
