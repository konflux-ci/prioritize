#!/usr/bin/env python3
""" Apply a set of rules on a project

The project id and the set of rules to apply is managed via a configuration file.
See the config directory for a template and examples.

This script accepts two arguments: a path to a configuration file and a token.
"""

import functools
import importlib
import os
import typing

import click
import jira

from utils.configuration import Config
from utils.jira import set_non_compliant_flag


@click.command(
    help=__doc__,
)
@click.option(
    "--dry-run",
    help="Do not update issues. Because of cascading changes not being taken into account, the output may be a subset of the real run.",
    is_flag=True,
)
@click.option(
    "-c",
    "--config-file",
    help="Configuration file",
    required=True,
)
@click.option(
    "-t",
    "--token",
    help="JIRA personal access token",
    default=os.environ.get("JIRA_TOKEN"),
    required=True,
)
def main(dry_run: bool, config_file: str, token: str) -> None:
    config = Config.load(config_file)
    Config.validate(config)

    jira_client = jira.client.JIRA(server=config["jira"]["url"], token_auth=token)
    jira_module = importlib.import_module("utils.jira")
    rules_modules = {
        "program": importlib.import_module("rules.program"),
        "team": importlib.import_module("rules.team"),
    }
    for automation in ["program", "team"]:
        for issue_type, issue_config in (
            config.get(automation + "_automation", {}).get("issues", {}).items()
        ):
            print(f"\n\n## Processing {issue_type}")
            collector = getattr(
                jira_module, issue_config.get("collector", "get_issues")
            )
            issues = collector(
                jira_client,
                config["jira"]["project-id"],
                config["jira"]["subquery"],
                issue_type,
            )
            issue_rules = [
                get_rule(rule, rules_modules[automation])
                for rule in issue_config.get("rules", [])
            ]
            group_rules = [
                get_rule(rule, rules_modules[automation])
                for rule in issue_config.get("group_rules", [])
            ]
            process_type(
                jira_client,
                issues,
                issue_rules,
                group_rules,
                dry_run,
                config["comments"]["footer"],
            )
    print("\nDone.")


def process_type(
    jira_client: jira.client.JIRA,
    issues: list[jira.resources.Issue],
    checks: list[callable],
    group_checks: list[callable],
    dry_run: bool,
    footer: str,
) -> None:
    count = len(issues)
    for index, issue in enumerate(issues):
        print(
            f"\n### [{index + 1}/{count}]\t{issue.key}: {issue.fields.summary}\t[{issue.fields.assignee}/{issue.fields.status}]"
        )
        context = {
            "comments": [],
            "jira_client": jira_client,
            "updates": [],
            "non-compliant": False,
        }
        for check in checks:
            check(issue, context, dry_run)

        set_non_compliant_flag(issue, context, dry_run)
        add_comment(issue, context, dry_run, footer)

    context = {
        "comments": [],
        "jira_client": jira_client,
        "updates": [],
        "non-compliant": False,
        "footer": footer,
    }
    for check in group_checks:
        check(issues, context, dry_run)


def add_comment(issue: jira.resources.Issue, context: dict, dry_run: bool, footer: str):
    if context["comments"]:
        if not dry_run:
            comment = "\n".join(context["comments"])
            if footer:
                comment = f"{comment}\n\n{footer}"
            context["jira_client"].add_comment(issue.key, comment)
    if context["updates"]:
        print("\n".join(context["updates"]))


def get_rule(rule: typing.Any, module):
    kwargs = {}
    if isinstance(rule, dict):
        kwargs = rule.get("kwargs", {})
        rule = rule["rule"]
    func = getattr(module, rule)
    return functools.partial(func, **kwargs)


if __name__ == "__main__":
    main()
