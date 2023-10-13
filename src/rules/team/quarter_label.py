from re import compile
from time import strftime

import jira
from utils.jira import update

today = strftime("%Y-%m-%d")


def check_quarter_label(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue is None:
        return

    updated = False
    re_quarter = compile("[0-9]{4}Q[1-4]")
    for label in parent_issue.fields.labels:
        if re_quarter.match(label) and label not in issue.fields.labels:
            context["updates"].append(f"  > Adding label: {label}.")
            if not dry_run:
                issue.fields.labels.append(label)
                updated = True
    for label in issue.fields.labels:
        if re_quarter.match(label) and label not in parent_issue.fields.labels:
            context["updates"].append(f"  < Removing label: {label}.")
            if not dry_run:
                issue.fields.labels.remove(label)
                updated = True
    if updated:
        update(issue, {"fields": {"labels": issue.fields.labels}})
