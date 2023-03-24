#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR=$(
    cd "$(dirname "$0")" >/dev/null || exit 1
    pwd
)
PROJECT_DIR=$(
    cd "$SCRIPT_DIR/../../.." >/dev/null || exit 1
    pwd
)

usage() {
    echo "
Usage:
    ${0##*/} [options]

Start the container. The container will be removed upon exit.

Optional arguments:
    -d, --debug
        Activate tracing/debug mode.
    -h, --help
        Display this message.

Example:
    ${0##*/} --debug
" >&2
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
        -d | --debug)
            set -x
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            exit 1
            ;;
        esac
        shift
    done
}

enter_container() {
    podman run \
        -it \
        --entrypoint "/bin/bash" \
        --rm \
        --volume "$PROJECT_DIR":"/workspace":Z \
        --workdir "/workspace" \
        "docker.io/python:3.11"
}

main() {
    parse_args "$@"
    enter_container
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    main "$@"
fi
