#!/usr/bin/env python3
""" Automatically prioritize JIRA stories attached to a JIRA feature

Problem: If features are prioritized up or down - that ranking doesn't cascade to stories.  In order
to plan sprints, you manually have to open tons of tabs, compare the priority of Features, find all
the epics on those features and then find all the stories for your team on those epics - and move
them up in your sprint planning backlog individually. What a pain!

This script attempts to automate that for you.

This script accepts two arguments: a feature id and a project id.  All of the stories of all of the
epics of the Feature will be prioritized up higher than the highest ranked story in the given
project.

"""

import argparse
import os
import sys

import click
import jira

PRIORITY = [
    "Undefined",
    "Minor",
    "Normal",
    "Major",
    "Critical",
    "Blocker",
]

DRY_RUN = False


@click.command(
    help=__doc__,
)
@click.option(
    "--dry-run",
    help="Do not update issues. Because of cascading changes not being taken into account, the output may be a subset of the real run.",
    is_flag=True,
)
@click.option(
    "-p",
    "--project-id",
    help="Name of the project we are prioritizing in",
    required=True,
)
@click.option(
    "-t",
    "--token",
    help="JIRA personal access token",
    default=os.environ.get("JIRA_TOKEN"),
    required=True,
)
@click.option(
    "-u",
    "--url",
    help="JIRA URL",
    default=os.environ.get("JIRA_URL", "https://issues.redhat.com"),
)
def main(dry_run: bool, project_id: str, token: str, url: str) -> None:
    global DRY_RUN
    DRY_RUN = dry_run
    jira_client = jira.client.JIRA(server=url, token_auth=token)

    config = {
        "issues": ["Epic", "Story"],
        "Parent Link": get_parent_link_fields_ids(jira_client),
    }

    for issue_type in config["issues"]:
        process_type(jira_client, project_id, issue_type, config)
    print("Done.")


def process_type(
    jira_client: jira.client.JIRA, project_id: str, issue_type: str, config: dict
) -> None:
    print(f"\n\n## Processing {issue_type}")

    issues = get_issues(jira_client, project_id, issue_type)
    parent_link_field_id = get_parent_link_field_id(issues, config["Parent Link"])

    for issue in issues:
        print(f"### {issue.key}")
        context = {
            "comments": [],
            "jira_client": jira_client,
            "parent_issue": None,
            "parent_link_field_id": parent_link_field_id,
            "updates": [],
        }
        check_parent_link(issue, context)
        check_priority(issue, context)

        set_non_compliant_flag(issue, context)
        add_comment(issue, context)


def get_parent_link_fields_ids(jira_client: jira.client.JIRA) -> list[str]:
    all_the_fields = jira_client.fields()
    link_names = ["Epic Link", "Feature Link", "Parent Link"]
    parent_link_fields_ids = [
        f["id"] for f in all_the_fields if f["name"] in link_names
    ]
    return parent_link_fields_ids


def get_issues(
    jira_client: jira.client.JIRA, project_id: str, issue_type: str
) -> list[jira.resources.Issue]:
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type} ORDER BY key ASC"
    print("  ?", query)
    results = jira_client.search_issues(query, maxResults=0)
    if not results:
        print(f"No Epic found via query: {query}")
        sys.exit(1)
    print("  =", f"{len(results)} results:", [r.key for r in results])
    return results


def get_parent_link_field_id(
    issues: list[jira.resources.Issue], field_ids: list[str]
) -> str:
    for issue in issues:
        for field_id in field_ids:
            if getattr(issue.fields, field_id) is not None:
                return field_id
    return ""


def get_max_priority(issues: list[jira.resources.Issue]) -> str:
    priority_ids = [PRIORITY.index(i.fields.priority.name) for i in issues]
    if priority_ids:
        max_priority = max(priority_ids)
    else:
        max_priority = 0
    return PRIORITY[max_priority]


def check_parent_link(issue: jira.resources.Issue, context: dict) -> None:
    if context["parent_link_field_id"]:
        parent_key = getattr(issue.fields, context["parent_link_field_id"])
        if parent_key is not None:
            context["parent_issue"] = context["jira_client"].issue(parent_key)
    if context["parent_issue"] is None:
        context["comments"].append(f"  * Issue is missing the link to its parent.")


def check_priority(issue: jira.resources.Issue, context: dict) -> None:
    related_issues = [
        context["jira_client"].issue(il.raw["outwardIssue"]["key"])
        for il in issue.fields.issuelinks
        if il.type.name == "Blocks" and "outwardIssue" in il.raw.keys()
    ]
    if context["parent_issue"] is not None:
        related_issues.append(context["parent_issue"])
    target_priority = get_max_priority(related_issues)
    if issue.fields.priority.name != target_priority:
        context["updates"].append(
            f"  > Issue priority set to '{target_priority}' (was '{issue.fields.priority.name}')."
        )
    if not DRY_RUN:
        issue.update(priority={"name": target_priority})


def set_non_compliant_flag(issue: jira.resources.Issue, context: dict) -> None:
    non_compliant_flag = "Non-compliant"
    has_non_compliant_flag = non_compliant_flag in issue.fields.labels
    if context["comments"]:
        print("\n".join(context["comments"]))
    if not DRY_RUN:
        if context["comments"]:
            if has_non_compliant_flag:
                context["comments"].clear()
            else:
                issue.fields.labels.append(non_compliant_flag)
                issue.update(fields={"labels": issue.fields.labels})
        elif not context["comments"] and has_non_compliant_flag:
            issue.fields.labels.remove(non_compliant_flag)
            issue.update(fields={"labels": issue.fields.labels})
            context["comments"].append("  * Issue is now compliant")


def add_comment(issue: jira.resources.Issue, context: dict):
    if context["comments"]:
        if not DRY_RUN:
            context["jira_client"].add_comment(
                issue.key, "\n".join(context["comments"])
            )
    if context["updates"]:
        print("\n".join(context["updates"]))


if __name__ == "__main__":
    main()
