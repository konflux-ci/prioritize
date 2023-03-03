#!/usr/bin/env python
""" If features are prioritized up or down - that rank doesn't cascade to stories.

This script accepts two arguments: a feature id and a project id.  All of the stories of all of the
epics of the Feature will be prioritized up higher than the highest ranked story in the given
project.

"""

import argparse
import os
import sys

import jira


def get_args():
    """
    Parse args from the command-line.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project",
        help="Name of the project we are prioritizing in",
    )
    parser.add_argument(
        "feature",
        help="Key of the feature we are prioritizing to the top",
    )
    return parser.parse_args()


args = get_args()

url = os.environ.get("JIRA_URL", "https://issues.redhat.com")
token = os.environ.get("JIRA_TOKEN")
if not token:
    print("Set JIRA_TOKEN environment variable to your JIRA personal access token")
    sys.exit(1)

JIRA = jira.client.JIRA(server=url, token_auth=token)

query = f"key={args.feature} and type=Feature"
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
query = f'issueFunction in issuesInEpics("key in ({epic_keys})") and project="{args.project}" and statusCategory != Done'
print(f"Looking up stories in {args.project} on those epics")
print("  > " + query)
stories = JIRA.search_issues(query)

query = f'project="{args.project}" ORDER BY Rank Desc'
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
