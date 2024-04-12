from time import strftime

import celpy
import jira

from utils.cel import issue_as_cel
from utils.jira import update

today = strftime("%Y-%m-%d")


def check_due_date(
    issue: jira.resources.Issue, context: dict, dry_run: bool, ignore: str = ""
) -> None:
    if ignore:
        env = celpy.Environment()
        program = env.program(env.compile(ignore))
        if program.evaluate(issue_as_cel(issue)):
            context["updates"].append(
                f"! Ignoring {issue.key} for due date rule, per cel expression {ignore}."
            )
            return

    related_issues = list(issue.raw["Context"]["Related Issues"]["Blocks"])
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue is not None:
        related_issues.append(parent_issue)
    if not related_issues:
        return

    due_date_id = issue.raw["Context"]["Field Ids"]["Due Date"]
    target_due_date, target_source = None, None
    for i in related_issues:
        related_due_date = getattr(i.fields, due_date_id)
        if related_due_date is None:
            continue
        if not target_due_date or target_due_date > related_due_date:
            target_due_date = related_due_date
            target_source = i

    due_date = getattr(issue.fields, due_date_id)
    if (target_due_date is None and due_date) or (
        target_due_date and (not due_date or due_date != target_due_date)
    ):
        if target_source:
            message = f"  * Updating Due Date to {target_due_date}, inherited from parent {target_source.key}."
        else:
            message = f"  * Updating Due Date to {target_due_date}."

        context["updates"].append(message)
        context["comments"].append(message)

        if not dry_run:
            update(issue, {"fields": {due_date_id: target_due_date}})

    # This check is just a notification message to the attention of the Scrum Leader.
    # The Target Date and Due Date should not be modified by the Assignee.
    # The Program Managers should have automation that will surface the impact of the
    # issue on their plans.
    end_date_id = issue.raw["Context"]["Field Ids"]["Target End Date"]
    end_date = getattr(issue.fields, end_date_id)
    if end_date and target_due_date and end_date > target_due_date:
        context["updates"].append(
            "  ? Target Date exceeds Due Date. You may want to notify the Program Managers."
        )
