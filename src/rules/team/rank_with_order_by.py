"""
Use the order of the JQL query to rank the issues.

Options:
- order_by: str, the order clause for the JQL query
- cascade: bool, if True, rank the children of the issues
"""

from atlassian import Jira

from utils.jira import get_children, get_issues, rank_issues


def check_rank_with_order_by(
    issues: list[dict],
    context: dict,
    dry_run: bool,
    order_by: str,
    cascade: bool = False,
) -> None:
    """Rerank all issues"""
    jira_client = context["jira_client"]

    ranked_issues = get_issues(
        jira_client,
        issues[0]["fields"]["project"]["key"],
        "",
        issues[0]["fields"]["issuetype"]["name"],
        order_by,
        False,
    )
    if cascade:
        new_ranking = []
        for issue in ranked_issues:
            new_ranking += _get_all_children_ranked(jira_client, issue, order_by)
    else:
        new_ranking = ranked_issues
    rank_field_id = issues[0]["Context"]["Field Ids"]["Rank"]
    old_ranking = sorted(
        new_ranking,
        key=lambda i: i["fields"][rank_field_id],
    )

    # Apply new ranking
    rank_issues(new_ranking, old_ranking, dry_run)


def _get_all_children_ranked(
    jira_client: Jira, issue: dict, order_by: str
) -> list[dict]:
    ranked_issues = [issue]
    children = get_children(jira_client, issue, order_by)
    # Ignored closed issues
    children = [
        c
        for c in children
        if c["fields"]["project"]["key"] == issue["fields"]["project"]["key"]
        and c["fields"]["status"]["statusCategory"]["name"] != "Done"
    ]
    for child in children:
        ranked_issues += _get_all_children_ranked(jira_client, child, order_by)
    return ranked_issues
