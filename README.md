# JIRA Hygiene scripts

- __automation__: This script is intended to run on a JIRA's project, looking for issues that don't meet expected Jira hygiene rules, fixing and/or commenting on any discovered issue. The function expects a configuration file, for which you can find a template in [config](./config/template.yaml).


Examples of rules that can be applied by __automation__:
* Hierarchy:
  * Epic must have a parent issue. The issue can be of any type.
  * Stories must have a parent Epic.
* Priority
  * An issue priority must match the highest priority of:
    * its parent
    * any of the issues blocked by this issue.
* Ranking
  * When 2 child issues belong to the same project, and their parent issues also belong to the
    same project, the child issues ranking must reflect the ranking of the parent issues.

## Available rules

| Rule | What it does |
|---|---|
| `check_parent_link` | Flags an issue as non-compliant when it has no parent link; supports a CEL `ignore` expression. |
| `check_priority` | Sets an issue’s priority to the highest priority found among its parent and blocking issues. |
| `check_due_date` | Sets the due date to the earliest due date among its parent and blocking issues; can flag a target-end date that exceeds it. |
| `check_due_date_by_fixversion` | Sets or pulls forward an issue’s due date to the earliest release date of its Fix Versions. |
| `check_target_dates` | Flags missing target dates for work under an in-progress parent, plus target start/end dates that are obsolete. |
| `check_quarter_label` | Synchronizes quarter labels matching `YYYYQn` between an issue and its parent. |
| `set_fix_version` | Adds the ancestor Outcome’s key as a Fix Version and removes other issue-key-like Fix Versions. |
| `sync_blocker_links_from_descendants` | Makes an Epic’s unresolved “is blocked by” links equal the union of its descendants’ blockers. |
| `set_status_from_children` | Recursively derives parent status from children: all To Do → New; all Done → Closed; any mixed/in-progress state → In Progress. |
| `check_rank` | Reranks related work as parent-based blocks, preserving project-specific ordering; optionally promotes in-progress parent blocks. |
| `check_rank_with_order_by` | Applies a ranking based on a supplied JQL `ORDER BY` clause, with optional recursive child ranking. |
| `check_timesensitive_rank` | Prioritizes items due within four months, preserves manually controlled items, and orders the backlog tail by RICE score. |
| `check_fixversion_rank` | Prioritizes items with a Fix Version releasing within six months, preserves the middle, and orders the backlog tail by RICE score. |
| `check_priority_from_rank` | Assigns priority from unified-backlog percentile: Critical (top 6.25%), Major (12.5%), Normal (25%), then Minor. |
| `check_priority_from_rank_by_component` | Assigns priority from an issue’s best percentile across its component backlogs; issues with no relevant component become Undefined. |
| `check_components` | Updates a parent’s components to precisely the union of its children’s components. |
| `check_target_end_date` | Sets a Feature/Outcome target-end estimate from the latest active child-Epic date only when at least 75% of active child Epics are estimated. |

## Development Environment

# VSCode

The [Remote Development](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) extension can be used to open the project in a container.

Everything should be setup for the project, including the debugger.

# Manually Starting a Container
A container is used to provide the base environment to develop and run the utility.

* Start a container with `./tools/developer/hack/start_container.sh`.
* The container will automatically be removed upon exit.

## Runtime Environment
A container is used to provide the base environment to run the utility.

* Run `./tools/release/hack/run.sh -- --config-file config/myproject.yaml --token '\$(cat ~/.config/tokens/jira.txt)'`.

## Usage notes 
The expecation is that a team would set up some automation to run this periodically (like in GitLab), and could set up and provide a token for a JIRA bot.
