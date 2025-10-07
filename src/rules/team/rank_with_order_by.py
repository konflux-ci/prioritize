"""
Use the order of the JQL query to rank the issues.

Options:
- order_by: str, the order clause for the JQL query
- cascade: bool, if True, rank the children of the issues
"""

import jira

from rules.team.rank import _set_rank
from utils.jira import get_children, get_issues


def check_rank_with_order_by(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
    order_by: str,
    cascade: bool = False,
) -> None:
    """Rerank all issues"""
    jira_client = context["jira_client"]

    ranked_issues = get_issues(
        jira_client,
        issues[0].get_field("project"),
        "",
        issues[0].get_field("issuetype"),
        order_by,
        False,
    )
    if cascade:
        new_ranking = []
        for issue in ranked_issues:
            new_ranking += _get_all_children_ranked(jira_client, issue, order_by)
    else:
        new_ranking = ranked_issues
    old_ranking = sorted(
        new_ranking,
        key=lambda i: i.get_field(issues[0].raw["Context"]["Field Ids"]["Rank"]),
    )

    # Apply new ranking
    _set_rank(jira_client, old_ranking, new_ranking, dry_run)


def _get_all_children_ranked(
    jira_client, issue: jira.resources.Issue, order_by: str
) -> list[jira.resources.Issue]:
    ranked_issues = [issue]
    children = get_children(jira_client, issue, order_by)
    # Ignored closed issues
    children = [
        c
        for c in children
        if c.get_field("project") == issue.get_field("project")
        and c.get_field("status").statusCategory.name != "Done"
    ]
    for child in children:
        ranked_issues += _get_all_children_ranked(jira_client, child, order_by)
    return ranked_issues
