import jira
from time import strftime

today = strftime("%Y-%m-%d")

def check_target_dates(issue: jira.resources.Issue, context: dict, dry_run: bool) -> None:
    start_date_id = issue.raw["Context"]["Field Ids"]["Target Start"]
    end_date_id = issue.raw["Context"]["Field Ids"]["Target End"]
    start_date = getattr(issue.fields, start_date_id)
    end_date = getattr(issue.fields, end_date_id)
    if start_date:
        if start_date < today and issue.fields.status in ["New", "Refinement"]:
            context["updates"].append(
                f"  > Issue Target Start Date is obsolete."
            )
    else:
        context["updates"].append(
            f"  > Issue Target Start Date unset."
        )
    if end_date:
        # Query ensure the issue is not closed
        if end_date < today:
            context["updates"].append(
            f"  > Issue Target End Date is obsolete."
        )
    else:
        context["updates"].append(
            f"  > Issue Target End Date unset."
        )
