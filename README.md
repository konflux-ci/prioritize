# Prioritize
JIRA utility that enforces the following rules:
* All Stories are linked to an Epic.
* All Stories have a priority greater or equal to their Epic.
* All Epics are linked to a Feature.
* All Epics have a priority greater or equal to their Feature.

## Development Environment
A container is used to provide the base environment to develop and run the utility.

* Start a container with `./tools/developer/hack/start_container.sh`.
* The container will automatically be removed upon exit.

## Runtime Environment
A container is used to provide the base environment to run the utility.

* Run `./tools/release/hack/run.sh -- [options]`.
