"""
Check if the target end date of an issue is consistent with the target end dates of its children.
The date is set if at least 75% of the children have a target end date, otherwise it is unset.'
"""

from utils.jira import update


def _listify(epics):
    ids = [epic["key"] for epic in epics]
    if len(ids) == 0:
        return "None"
    elif len(ids) == 1:
        return ids[0]
    elif len(ids) == 2:
        first, last = ids
        return f"{first} and {last}"
    else:
        first, last = ids[:-1], ids[-1]
        return f"{', '.join(first)} and {last}"


def check_target_end_date(issue: dict, context: dict, dry_run: bool) -> None:
    target_end_id = issue["Context"]["Field Ids"]["Target End Date"]
    target_end_date, target_source = None, None
    estimated_children = []
    unestimated_children = []

    children_src = issue["Context"]["Related Issues"]["Children"]
    active_child_count = 0
    for i in children_src:
        if i["fields"]["status"]["statusCategory"]["name"] in ["Done", "Closed"]:
            continue
        if i["fields"]["issuetype"]["name"] != "Epic":
            continue
        active_child_count += 1
        related_target_end_date = i["fields"][target_end_id]
        if related_target_end_date is None:
            unestimated_children.append(i)
            continue
        estimated_children.append(i)
        if not target_end_date or target_end_date < related_target_end_date:
            target_end_date = related_target_end_date
            target_source = i

    # Only propagate estimates if "most" children have estimates
    if active_child_count:
        proportion_estimated = float(len(estimated_children)) / active_child_count
    else:
        proportion_estimated = 0
    estimation_threshold = 0.75
    if proportion_estimated < estimation_threshold:
        target_end_date = None

    # Preserve manually-set target end dates on features with no active children
    # (If a feature has no children but has a target end date, it was set manually)
    end_date = issue["fields"][target_end_id]
    if active_child_count == 0 and end_date is not None:
        return
    if (target_end_date is None and end_date) or (
        target_end_date and (not end_date or end_date != target_end_date)
    ):
        if proportion_estimated < estimation_threshold:
            message = f"  * Updating Target end date estimate to {target_end_date}."
            message += f"\n  * Only {int(proportion_estimated * 100)}% of children have estimates."
            message += f"\n  * Set target end dates on child epic(s) {_listify(unestimated_children)} to influence the target end date of this Feature."
        else:
            message = f"  * Updating Target end date estimate to {target_end_date}, propagated from child {target_source['key'] if target_source else None}."

        context["updates"].append(message)
        context["comments"].append(message)

        if not dry_run:
            update(issue, {target_end_id: [{"set": target_end_date}]})
