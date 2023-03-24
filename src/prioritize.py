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


@click.command(
    help=__doc__,
)
@click.option(
    "-f",
    "--feature-id",
    help="Key of the feature we are prioritizing to the top",
    required=True,
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
def main(feature_id: str, project_id: str, token: str, url: str) -> None:
    JIRA = jira.client.JIRA(server=url, token_auth=token)

    query = f"key={feature_id} and type=Feature"
    print("Confirming the Feature exists:")
    print("  > " + query)
    results = JIRA.search_issues(query)
    if not results:
        print(f"Feature not found via query: {query}")
        sys.exit(1)
    feature = results[0]

    query = f'issueFunction in portfolioChildrenOf("key={feature}")'
    print("Looking up epics on the feature")
    print("  > " + query)
    epics = JIRA.search_issues(query)

    if not epics:
        print("No epics found.")
        sys.exit(1)

    epic_keys = ",".join([epic.key for epic in epics])
    query = f'issueFunction in issuesInEpics("key in ({epic_keys})") and project="{project_id}" and statusCategory != Done'
    print(f"Looking up stories in {project_id} on those epics")
    print("  > " + query)
    stories = JIRA.search_issues(query)

    query = f'project="{project_id}" ORDER BY Rank Asc'
    print("Finding current highest ranked story in the project")
    print("  > " + query)
    current_order = JIRA.search_issues(query)
    highest = current_order[0]

    print()
    print(f"Moving {len(stories)} stories higher than {highest.key}")
    for story in stories:
        if story == highest:
            print(f"  Ignoring {story.key}. It is already ranked highest.")
            continue
        print(f"  Moving rank of {url}/browse/{story.key} above {highest.key}")
        JIRA.rank(issue=story.key, prev_issue=highest.key)
    print("Done.")


if __name__ == "__main__":
    main()
