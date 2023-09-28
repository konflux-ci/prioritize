from time import strftime

import jira

from utils.jira import refresh, update

today = strftime("%Y-%m-%d")


def check_target_end_date(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    children = issue.raw["Context"]["Related Issues"]["Children"]

    if not children:
        return

    target_end_id = issue.raw["Context"]["Field Ids"]["Target End Date"]
    target_end_date, target_source = None, None
    for i in children:
        related_target_end_date = getattr(i.fields, target_end_id)
        if related_target_end_date is None:
            continue
        if not target_end_date or target_end_date < related_target_end_date:
            target_end_date = related_target_end_date
            target_source = i

    end_date = getattr(issue.fields, target_end_id)
    if (target_end_date is None and end_date) or (
        target_end_date and (not end_date or end_date != target_end_date)
    ):
        if target_source:
            context["updates"].append(
                f"  > Updating Target end Date to {target_end_date}, propagated from {target_source.key}."
            )
        else:
            context["updates"].append(
                f"  > Updating Target end Date to {target_end_date}."
            )
        if not dry_run:
            update(issue, {"fields": {target_end_id: target_end_date}})
