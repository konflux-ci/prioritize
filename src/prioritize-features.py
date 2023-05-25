#!/usr/bin/env python3
""" Automatically prioritize features of one label above others

Problem: If you use labels to track different categories of features and you want to prioritize all
features of one label above others (treat it as the focus), you have to manually comb through the
backlog and move the features up (increase their rank) for each one. If features in that label have
different priority-field settings, you don't want to move them all to the top; you just want to move
them above other features of the same priority field setting. What a pain!

This script attempts to automate that for you.

This script accepts one argument: a label. All of the features in that label will be prioritized up
higher than the highest ranked feature for each priority-field tier. (e.g., all Blocker features in
the label will be ranked above all other Blocker features. All Critical features in the label will
be ranked above all other Critical features. All Major features etc..)

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
    help="Do not update issues.",
    is_flag=True,
)
@click.option(
    "-l",
    "--label",
    help="Label we are prioritizing",
    required=True,
)
@click.option(
    "-p",
    "--project-id",
    help="Project that we are prioritizing in",
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
def main(dry_run: bool, label: str, project_id: str, token: str, url: str) -> None:
    global DRY_RUN
    DRY_RUN = dry_run
    jira_client = jira.client.JIRA(server=url, token_auth=token)

    all_fields = jira_client.fields()
    jira_name_map = {field["name"]: field["id"] for field in all_fields}
    rank_key = jira_name_map["Rank"]

    config = {
        "issues": ["Feature"],
        "rank_key": rank_key,
    }

    for issue_type in config["issues"]:
        process_type(jira_client, label, project_id, issue_type, config)
    print("Done.")


def process_type(
    jira_client: jira.client.JIRA,
    label: str,
    project_id: str,
    issue_type: str,
    config: dict,
) -> None:
    print(f"\n\n## Processing {issue_type}")

    priorities = PRIORITY
    issues = get_issues(jira_client, label, issue_type)
    top_issues = get_highest_ranked_issues(
        jira_client, priorities, project_id, issue_type
    )

    for issue in issues:
        print(f"### {issue.key}")
        context = {
            "updates": [],
            "jira_client": jira_client,
            "rank_key": config["rank_key"],
        }
        check_rank(issue, context, top_issues)
        add_comment(issue, context)


def get_highest_ranked_issues(
    jira_client: jira.client.JIRA,
    priorities: list[str],
    project_id: str,
    issue_type: str,
) -> dict:
    """Return a dict of the highest ranked issues with each priority"""
    results = {}
    for priority in priorities:
        query = f"priority={priority} AND project={project_id} AND type={issue_type} ORDER BY Rank ASC"
        issues = jira_client.search_issues(query, maxResults=1)
        if not issues:
            print(f"No {issue_type} found via query: {query}")
            sys.exit(1)
        results[priority] = issues[0]
    return results


def get_issues(
    jira_client: jira.client.JIRA, label: str, issue_type: str
) -> list[jira.resources.Issue]:
    query = f"labels={label} AND resolution=Unresolved AND type={issue_type} ORDER BY Rank DESC"
    print("  ?", query)
    results = jira_client.search_issues(query, maxResults=0)
    if not results:
        print(f"No {issue_type} found via query: {query}")
        sys.exit(1)
    print("  =", f"{len(results)} results:", [r.key for r in results])
    return results


def get_max_priority(issues: list[jira.resources.Issue]) -> str:
    priority_ids = [PRIORITY.index(i.fields.priority.name) for i in issues]
    if priority_ids:
        max_priority = max(priority_ids)
    else:
        max_priority = 0
    return PRIORITY[max_priority]


def check_rank(issue: jira.resources.Issue, context: dict, top_issues: dict) -> None:
    priority = issue.fields.priority.name
    top_issue = top_issues[priority]
    top_issues[priority] = issue
    context["updates"].append(
        f"  > Issue rank of {issue.key} moved above {top_issue.key}"
    )
    if not DRY_RUN:
        context["jira_client"].rank(issue.key, next_issue=top_issue.key)


def add_comment(issue: jira.resources.Issue, context: dict):
    if context["updates"]:
        print("\n".join(context["updates"]))


if __name__ == "__main__":
    main()
