# JIRA Hygiene scripts
There are currently 3 functions in this repo that try to ease Jira toil in different circumstances. 
- __prioritize-features__: This is intended to run against a parent of a project's features (like an outcome), and prioritizes all features of that parent above features associated with other parents.
- __program_automation__: This is intended to run against a project to make it easier to push information dwon from a feature (like setting a feature's due date on all child issues), and eventually, pull information up to the feature level (like setting a feature's end date as the farthest end date of its epics).
- __team_hygiene__: This is intended to run on a team's project, looking for issues that don't meet expected Jira hygiene rules, commenting on any discovered issue.
More detailed inforation can be found in each function's code. Addiiotnal functionality could be added in the future.

Examples of things team_hygiene looks at: 
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

## Development Environment
A container is used to provide the base environment to develop and run the utility.

* Start a container with `./tools/developer/hack/start_container.sh`.
* The container will automatically be removed upon exit.

## Runtime Environment
A container is used to provide the base environment to run the utility.

* Run `./tools/release/hack/run.sh -- --project-id MYPROJECT --token '\$(cat ~/.config/tokens/jira.txt)'`.

## Usage notes 
The expecation is that a team would set up some automation to run this periodically (like in GitLab), and could set up and provide a token for a JIRA bot.
