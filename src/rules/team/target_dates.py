from time import strftime

today = strftime("%Y-%m-%d")


def check_target_dates(issue: dict, context: dict, dry_run: bool) -> None:
    start_date_id = issue["Context"]["Field Ids"]["Target Start Date"]
    end_date_id = issue["Context"]["Field Ids"]["Target End Date"]
    start_date = issue["fields"][start_date_id]
    end_date = issue["fields"][end_date_id]

    parent_is_inprogress = False
    parent_issue = issue["Context"]["Related Issues"]["Parent"]
    if parent_issue:
        parent_is_inprogress = (
            parent_issue["fields"]["status"]["statusCategory"]["name"] == "In Progress"
        )

    if start_date:
        if start_date < today and issue["fields"]["status"]["name"] in [
            "New",
            "Refinement",
        ]:
            context["updates"].append("  > Issue Target Start Date is obsolete.")
    elif parent_is_inprogress:
        context["updates"].append("  * Issue Target Start Date unset.")
    if end_date:
        # Query ensure the issue is not closed
        if end_date < today:
            context["updates"].append("  * Issue Target End Date is obsolete.")
    elif parent_is_inprogress:
        context["updates"].append("  * Issue Target End Date unset.")
