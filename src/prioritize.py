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
    JIRA = jira.client.JIRA(server=url, token_auth=token)

    config = {
        "Epic": {
            "Parent Link": "customfield_12318341",
        },
        "Story": {
            "Parent Link": "customfield_12311140",
        },
    }

    for issue_type, key_config in config.items():
        process_type(JIRA, project_id, issue_type, key_config)
    print("Done.")


def process_type(JIRA, project_id: str, issue_type: str, key_config: dict) -> None:
    print("\n\n## Processing {key_type}")
    for issue in get_issues(JIRA, project_id, issue_type):
        parent_key = getattr(issue.fields, key_config["Parent Link"])
        if parent_key is None:
            comment(JIRA, issue.key, f"{issue_type} is missing the link to its parent.")
            continue
        parent = JIRA.issue(parent_key)
        check_priority(JIRA, issue, parent)


def get_issues(JIRA, project_id, issue_type):
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type} ORDER BY key ASC"
    print("  ?", query)
    results = JIRA.search_issues(query, maxResults=0)
    if not results:
        print(f"No Epic found via query: {query}")
        sys.exit(1)
    print("  =", [r.key for r in results], f"\n[{len(results)}]\n")
    return results


def comment(jira, key, comment):
    print(f"[{key}] {comment}")
    # jira.comment(epic.key, comment)


def get_priority(issue):
    return PRIORITY.index(issue.fields.priority.name)


def check_priority(JIRA, issue, parent):
    related_issues = [
        JIRA.issue(il.raw["outwardIssue"]["key"])
        for il in issue.fields.issuelinks
        if il.type.name == "Blocks" and "outwardIssue" in il.raw.keys()
    ]
    related_issues.append(parent)
    target_priority = max([get_priority(i) for i in related_issues])
    if get_priority(issue) != target_priority:
        comment(
            JIRA, issue.key, "Issue priority does not match Parent or Blocked issues"
        )


if __name__ == "__main__":
    main()
