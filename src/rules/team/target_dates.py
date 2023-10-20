from time import strftime

import jira

today = strftime("%Y-%m-%d")


def check_target_dates(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    start_date_id = issue.raw["Context"]["Field Ids"]["Target start"]
    end_date_id = issue.raw["Context"]["Field Ids"]["Target end"]
    start_date = getattr(issue.fields, start_date_id)
    end_date = getattr(issue.fields, end_date_id)

    parent_is_inprogress = False
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue:
        parent_is_inprogress = (
            parent_issue.fields.status.statusCategory.name == "In Progress"
        )

    if start_date:
        if start_date < today and issue.fields.status in ["New", "Refinement"]:
            context["updates"].append(f"  > Issue Target Start date is obsolete.")
    elif parent_is_inprogress:
        context["updates"].append(f"  * Issue Target Start date unset.")
    if end_date:
        # Query ensure the issue is not closed
        if end_date < today:
            context["updates"].append(f"  * Issue Target End date is obsolete.")
    elif parent_is_inprogress:
        context["updates"].append(f"  * Issue Target End date unset.")
