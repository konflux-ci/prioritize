# Prioritize
JIRA utility that enforces the following rules:
* All Stories are linked to an Epic.
* All Stories have a priority greater or equal to their Epic.
* All Epics are linked to a Feature.
* All Epics have a priority greater or equal to their Feature.

## Environment
A container is used to provide the base environment to develop and run the utility.

* Start a container with `./tools/developer/hack/start_container.sh`.
* The container will automatically be removed upon exit.

## Installation

* Start a container (c.f. `Environment`)
* Once in the container, run `./tools/developer/hack/setup_devenv.sh`.

# Usage

* Start a container (c.f. `Environment`)
* Once in the container, run `./tools/release/hack/setup_env.sh`.
* You can then run the tool with `./src/prioritize.py --feature TEST-123 --project TEST --token Ab123cD456wx789yz0`
