from re import compile

import jira
import utils.jira


def set_fix_version(issue: jira.resources.Issue, context: dict, dry_run: bool) -> None:
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue is None:
        return
    utils.jira.preprocess(context["jira_client"], [parent_issue])
    outcome_issue = utils.jira.get_parent(context["jira_client"], parent_issue)
    if outcome_issue is None or outcome_issue.fields.issuetype.name != "Outcome":
        version_name = None
    else:
        version_name = outcome_issue.key

    fix_versions = getattr(issue.fields, "fixVersions", [])
    updated = False

    re_issue_key = compile("[A-Z]*-[0-9]*")
    for fv in fix_versions.copy():
        if re_issue_key.match(fv.name) and fv.name != version_name:
            updated = True
            fix_versions.remove(fv)
            context["updates"].append(f"  > Removing Fix Version: {fv.name}.")

    if version_name and version_name not in [fv.name for fv in fix_versions]:
        updated = True
        context["updates"].append(f"  > Adding Fix Version: {version_name}.")
        version = utils.jira.get_version(
            context["jira_client"],
            issue.key.split("-")[0],
            outcome_issue.key,
            outcome_issue.fields.summary,
        )
        fix_versions.append(version)

    if updated and not dry_run:
        utils.jira.update(
            issue,
            {
                "fields": {
                    "fixVersions": [{"name": fv.name} for fv in fix_versions],
                },
            },
        )
