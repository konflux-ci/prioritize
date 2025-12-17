"""
Set priority on issues based on the parent issue's priority.

If the issue has a related issue of higher priority, the issue will be set to that higher priority.
This allows for an issue to have a higher priority than its parent issue, for example when it is a
blocker for another issue.
"""

from utils.jira import refresh, update

PRIORITY = [
    "Undefined",
    "Minor",
    "Normal",
    "Major",
    "Critical",
    "Blocker",
]


def _get_max_priority(issues: list[dict]) -> str:
    max_priority = 0
    for issue in issues:
        if issue["fields"]["priority"] is not None:
            priority_index = PRIORITY.index(issue["fields"]["priority"]["name"])
            if priority_index > max_priority:
                max_priority = priority_index
    return PRIORITY[max_priority]


def check_priority(issue: dict, context: dict, dry_run: bool) -> None:
    related_issues = list(issue["Context"]["Related Issues"]["Blocks"])
    parent_issue = issue["Context"]["Related Issues"]["Parent"]

    # Do not update priority if there are no related issues or parent issue
    if not related_issues and not parent_issue:
        return

    if parent_issue is not None:
        refresh(parent_issue)
        related_issues.append(parent_issue)
    target_priority = _get_max_priority(related_issues)
    current_priority = issue["fields"]["priority"]["name"]
    if current_priority != target_priority:
        context["updates"].append(
            f"  > Issue priority set to '{target_priority}' (was '{current_priority}')."
        )
        if not dry_run:
            update(issue, {"priority": [{"set": {"name": target_priority}}]})
