#!/usr/bin/env python3
""" Automatically propagate attributes around the JIRA hierarchy

Problem: If a product manager sets a due date on a Feature, that due date should appear on all epics that are children of that Feature. If all teams set a "Target end" estimate on their epic, then the furthest out of those estimates should appear on the common Feature. Manually copying all of that stuff is a pain!

This script attempts to automate that for you.

This script accepts two arguments: a project id and a token.

* All of the epics of all of the features in that project will have their due dates aligned to the
  Features that are their parents.
* (In a future iteration of this script) all of the features in that project will have their "Target
  end" dates aligned to the most distant "Target end" date set on their child epics.
"""

import os
from collections import OrderedDict

import click
import jira

import rules.program
import rules.team
from utils.jira import get_child_issues, get_issues, set_non_compliant_flag, update


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

    config = OrderedDict()
    config["Epic"] = [
        rules.team.check_due_date,
    ]
    config["Feature"] = [
        rules.program.check_target_end_date,
    ]
    config["Outcome"] = [
        rules.program.check_target_end_date,
    ]
    collectors = {
        "Outcome": get_issues,
        "Feature": get_issues,
        "Epic": get_child_issues,
    }

    for issue_type in config.keys():
        print(f"\n\n## Processing {issue_type}")
        collector = collectors[issue_type]
        issues = collector(jira_client, project_id, issue_type)
        process_type(jira_client, issues, config[issue_type], dry_run)

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
