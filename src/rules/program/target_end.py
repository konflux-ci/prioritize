from time import strftime

import jira

from utils.jira import refresh, update

today = strftime("%Y-%m-%d")


def check_target_end_date(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:

    target_end_id = issue.raw["Context"]["Field Ids"]["Target End Date"]
    target_end_date, target_source = None, None
    estimated_children = 0

    children = issue.raw["Context"]["Related Issues"]["Children"]
    children = [child for child in children if (
        child.fields.status.statusCategory.name != 'Done' or
        getattr(child.fields, target_end_id)
    )]

    for i in children:
        related_target_end_date = getattr(i.fields, target_end_id)
        if related_target_end_date is None:
            continue
        estimated_children += 1
        if not target_end_date or target_end_date < related_target_end_date:
            target_end_date = related_target_end_date
            target_source = i

    # Only propagate estimates if "most" children have estimates
    if len(children):
        proportion_estimated = float(estimated_children) / len(children)
    else:
        proportion_estimated = 0
    estimation_threshold = 0.75
    if proportion_estimated < estimation_threshold:
        target_end_date = None

    end_date = getattr(issue.fields, target_end_id)
    if (target_end_date is None and end_date) or (
        target_end_date and (not end_date or end_date != target_end_date)
    ):
        if proportion_estimated < estimation_threshold:
            context["updates"].append(
                f"  > Updating Target end Date to {target_end_date}. Only {int(proportion_estimated * 100)}% of children have estimates."
            )
        else:
            context["updates"].append(
                f"  > Updating Target end Date to {target_end_date}, propagated from {getattr(target_source, 'key', None)}."
            )

        if not dry_run:
            update(issue, {"fields": {target_end_id: target_end_date}})
