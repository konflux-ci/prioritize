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
    ${0##*/} [options] -- [options]

Run the utility in a container. The container will be removed upon exit.

Optional arguments:
    -d, --debug
        Activate tracing/debug mode.
    -h, --help
        Display this message.

Example:
    ${0##*/} --debug -- --project-id MYPROJECT --token '\$(cat ~/.config/tokens/jira.txt)'
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
        --)
            shift
            OPTIONS=( "$@" )
            break
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

build_container() {
    podman build \
        -f "$SCRIPT_DIR/../container/Dockerfile" \
        --tag "$IMAGE_TAG" \
        "$SCRIPT_DIR/.."
}

enter_container() {
    podman run \
        -it \
        --hostname "${IMAGE_TAG//:/__}" \
        --rm \
        --volume "$PROJECT_DIR":"/workspace":Z \
        "$IMAGE_TAG" \
        "/workspace/src/jira_hygiene.py" "${OPTIONS[@]}"
}

main() {
    parse_args "$@"
    IMAGE_TAG="jira_hygiene:release"
    build_container
    enter_container
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    main "$@"
fi
