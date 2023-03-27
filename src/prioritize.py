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


@click.command(
    help=__doc__,
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
def main(project_id: str, token: str, url: str) -> None:
    jira_client = jira.client.JIRA(server=url, token_auth=token)

    config = {
        "issues": ["Epic", "Story"],
        "Parent Link": get_parent_link_ids(jira_client),
    }

    for issue_type in config["issues"]:
        process_type(jira_client, project_id, issue_type, config)
    print("Done.")


def process_type(jira_client, project_id: str, issue_type: str, config: dict) -> None:
    print(f"\n\n## Processing {issue_type}")
    parent_link_field_id = ""
    for issue in get_issues(jira_client, project_id, issue_type):
        if not parent_link_field_id:
            parent_link_field_id = [
                f for f in config["Parent Link"] if hasattr(issue.fields, f)
            ][0]
        context = {
            "comments": [],
            "jira_client": jira_client,
            "parent_issue": None,
            "parent_link_field_id": parent_link_field_id,
        }
        check_parent_link(issue, context)
        check_priority(issue, context)
        if context["comments"]:
            comment_text = "".join([f"\n  * {c}" for c in context["comments"]])
            print(f"[{issue.key}] {comment_text}")
            # jira_client.comment(issue.key, comment_text)


def get_parent_link_ids(JIRA):
    all_the_fields = JIRA.fields()
    link_names = ["Epic Link", "Feature Link", "Parent Link"]
    parent_link_ids = [f["id"] for f in all_the_fields if f["name"] in link_names]
    return parent_link_ids


def get_issues(jira_client, project_id, issue_type):
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type} ORDER BY key ASC"
    print("  ?", query)
    results = jira_client.search_issues(query, maxResults=0)
    if not results:
        print(f"No Epic found via query: {query}")
        sys.exit(1)
    print("  =", [r.key for r in results], f"\n[{len(results)}]\n")
    return results


def get_max_priority(issues: list[jira.resources.Issue]) -> str:
    priority_ids = [PRIORITY.index(i.fields.priority.name) for i in issues]
    if priority_ids:
        max_priority = max(priority_ids)
    else:
        max_priority = 0
    return PRIORITY[max_priority]


def check_parent_link(issue: jira.resources.Issue, context: dict) -> None:
    parent_key = getattr(issue.fields, context["parent_link_field_id"])
    parent_issue = None
    if parent_key is None:
        context["comments"].append(f"Issue is missing the link to its parent.")
    else:
        context["parent_issue"] = context["jira_client"].issue(parent_key)


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
        context["comments"].append(
            f"Issue priority ({issue.fields.priority.name}) set to {target_priority}."
        )
        # issue.update(priority={"name": target_priority})


if __name__ == "__main__":
    main()
