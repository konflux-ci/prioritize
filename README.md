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
