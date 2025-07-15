from time import strftime

import jira

from utils.jira import update

today = strftime("%Y-%m-%d")


def listify(epics):
    ids = [epic.key for epic in epics]
    if len(ids) == 0:
        raise ValueError("Cannot listify empty list")
    elif len(ids) == 1:
        return ids[0]
    elif len(ids) == 2:
        first, last = ids
        return f"{first} and {last}"
    else:
        first, last = ids[:-1], ids[-1]
        return f"{', '.join(first)} and {last}"


def check_target_end_date(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    target_end_id = issue.raw["Context"]["Field Ids"]["Target End Date"]
    target_end_date, target_source = None, None
    estimated_children = []
    unestimated_children = []

    children = issue.raw["Context"]["Related Issues"]["Children"]
    children = [
        child for child in children if child.fields.status.statusCategory.name != "Done"
    ]

    for i in children:
        related_target_end_date = getattr(i.fields, target_end_id)
        if related_target_end_date is None:
            unestimated_children.append(i)
            continue
        estimated_children.append(i)
        if not target_end_date or target_end_date < related_target_end_date:
            target_end_date = related_target_end_date
            target_source = i

    # Only propagate estimates if "most" children have estimates
    if len(children):
        proportion_estimated = float(len(estimated_children)) / len(children)
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
            message = f"  * Updating Target end date estimate to {target_end_date}."
            message += f"\n  * Only {int(proportion_estimated * 100)}% of children have estimates."
            message += f"\n  * Set target end dates on child epic(s) {listify(unestimated_children)} to influence the target end date of this Feature."
        else:
            message = f"  * Updating Target end date estimate to {target_end_date}, propagated from child {getattr(target_source, 'key', None)}."

        context["updates"].append(message)
        context["comments"].append(message)

        if not dry_run:
            update(issue, {"fields": {target_end_id: target_end_date}})
