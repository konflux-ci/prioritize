"""
Set the fix version of an issue to the key of the outcome issue.
"""

from re import compile

import utils.jira


def set_fix_version(issue: dict, context: dict, dry_run: bool) -> None:
    parent_issue = issue["Context"]["Related Issues"]["Parent"]
    if parent_issue is None:
        return
    utils.jira.preprocess(context["jira_client"], [parent_issue])
    outcome_issue = utils.jira.get_parent(context["jira_client"], parent_issue)
    if (
        outcome_issue is None
        or outcome_issue["fields"]["issuetype"]["name"] != "Outcome"
    ):
        version_name = None
    else:
        version_name = outcome_issue["key"]

    fix_versions = issue["fields"]["fixVersions"]
    data = []

    re_issue_key = compile("[A-Z]*-[0-9]*")
    for fv in fix_versions.copy():
        fv_name = (
            fv.get("name", "") if isinstance(fv, dict) else getattr(fv, "name", "")
        )
        if re_issue_key.match(fv_name) and fv_name != version_name:
            context["updates"].append(f"  > Removing Fix Version: {fv_name}.")
            data.append({"remove": {"name": fv_name}})

    if version_name and version_name not in [
        fv.get("name", "") if isinstance(fv, dict) else getattr(fv, "name", "")
        for fv in fix_versions
    ]:
        context["updates"].append(f"  > Adding Fix Version: {version_name}.")
        version = utils.jira.get_version(
            context["jira_client"],
            issue["fields"]["project"],
            outcome_issue["key"],
        )
        data.append({"add": {"name": version["name"]}})

    if data and not dry_run:
        utils.jira.update(issue, {"fixVersions": data})
