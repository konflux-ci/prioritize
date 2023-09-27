#!/usr/bin/env python3
""" Automatically prioritize/rank JIRA stories attached to a JIRA feature

Problem: If features are prioritized/ranked up or down - that action doesn't cascade to
stories.  In order to plan sprints, you manually have to open tons of tabs, compare the
priority/ranking of Features, find all the epics on those features and then find all the
stories for your team on those epics - and move them up in your sprint planning backlog
individually. What a pain!

This script attempts to automate that for you.

This script accepts two arguments: a project id and a token.  All of the stories of
all of the epics of the project will be checked against their parent to calculate the
right priority/rank.

Issues that do not have a parent will be labelled as 'Non-compliant'.
"""

import os

import click
import jira
from collections import OrderedDict

import rules.team
from utils.jira import get_child_issues, update, set_non_compliant_flag


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
    jira_client = jira.client.JIRA(server=url, token_auth=token)

    checks = [
        rules.team.check_due_date,
    ]

    print(f"\n\n## Processing epics")
    issues = get_child_issues(jira_client, project_id, ["Epic"])
    process_type(jira_client, issues, checks, dry_run)
    print("\nDone.")


def process_type(
    jira_client: jira.client.JIRA,
    issues: list[jira.resources.Issue],
    checks: list[callable],
    dry_run: bool,
) -> None:
    count = len(issues)
    for index, issue in enumerate(issues):
        print(
            f"\n### [{index+1}/{count}]\t{issue.key}: {issue.fields.summary}\t[{issue.fields.assignee}/{issue.fields.status}]"
        )
        context = {
            "comments": [],
            "jira_client": jira_client,
            "updates": [],
        }
        for check in checks:
            check(issue, context, dry_run)

        set_non_compliant_flag(issue, context, dry_run)
        add_comment(issue, context, dry_run)


def add_comment(issue: jira.resources.Issue, context: dict, dry_run: bool):
    if context["comments"]:
        if not dry_run:
            context["jira_client"].add_comment(
                issue.key, "\n".join(context["comments"])
            )
    if context["updates"]:
        print("\n".join(context["updates"]))


if __name__ == "__main__":
    main()
