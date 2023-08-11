import jira
from time import strftime
from utils.jira import refresh, update

today = strftime("%Y-%m-%d")


def check_due_date(issue: jira.resources.Issue, context: dict, dry_run: bool) -> None:
    related_issues = list(issue.raw["Context"]["Related Issues"]["Blocks"])
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue is not None:
        related_issues.append(parent_issue)
    if not related_issues:
        return

    due_date_id = issue.raw["Context"]["Field Ids"]["Due Date"]
    target_due_date = None
    for i in related_issues:
        related_due_date = getattr(i.fields, due_date_id)
        if related_due_date is None:
            continue
        if not target_due_date or target_due_date > related_due_date:
            target_due_date = related_due_date

    due_date = getattr(issue.fields, due_date_id)
    if (target_due_date is None and due_date) or (
        target_due_date and (not due_date or due_date != target_due_date)
    ):
        context["updates"].append(f"  > Updating Due Date to {target_due_date}.")
        if not dry_run:
            update(issue, {"fields": {due_date_id: target_due_date}})
