# JIRA Hygiene
Issues are expected to satisfy the following constraing:
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
