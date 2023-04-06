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

import os

import click
import jira

import rules
from utils.jira import get_issues


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

    context = {
        "issues": get_issues(jira_client, project_id, ["Epic", "Story"]),
    }

    for issue_type, issues in context["issues"].items():
        print(f"\n\n## Processing {issue_type}")
        process_type(jira_client, issues, dry_run)
    print("\nDone.")


def process_type(
    jira_client: jira.client.JIRA, issues: list[jira.resources.Issue], dry_run: bool
) -> None:
    count = len(issues)
    for index, issue in enumerate(issues):
        print(
            f"\n### [{index+1}/{count}]\t{issue.key}: {issue.fields.summary}\t[{issue.fields.assignee}]"
        )
        context = {
            "comments": [],
            "jira_client": jira_client,
            "updates": [],
        }
        rules.check_parent_link(issue, context)
        rules.check_priority(issue, context, dry_run)

        set_non_compliant_flag(issue, context, dry_run)
        add_comment(issue, context, dry_run)
    rules.check_rank(issues, context, dry_run)


def set_non_compliant_flag(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    non_compliant_flag = "Non-compliant"
    has_non_compliant_flag = non_compliant_flag in issue.fields.labels
    if context["comments"]:
        print("\n".join(context["comments"]))
    if not dry_run:
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
