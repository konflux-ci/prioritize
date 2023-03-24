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

Run the tool.

Mandatory arguments:
    -f, --feature FEATURE_ID
        Feature ID.
        Example: 'STONE-248'
    -p, --project PROJECT_ID
        Project ID.
        Example: 'ASC'
    -t, --token JIRA_TOKEN
        JIRA token.

Optional arguments:
    -d, --debug
        Activate tracing/debug mode.
    -h, --help
        Display this message.

Example:
    ${0##*/} --feature STONE-248 --project ASC --token Ab123cD456wx789yz0
" >&2
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
        -f | --feature)
            shift
            FEATURE_ID="$1"
            ;;
        -p | --project)
            shift
            PROJECT_ID="$1"
            ;;
        -t | --token)
            shift
            JIRA_TOKEN="$1"
            ;;
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

    if [[ -z "${JIRA_TOKEN:-}" ]]; then
        printf "JIRA_TOKEN is not set\n\n" >&2
        usage
        exit 1
    fi
    if [[ -z "${FEATURE_ID:-}" ]]; then
        printf "FEATURE_ID is not set\n\n" >&2
        usage
        exit 1
    fi
    if [[ -z "${PROJECT_ID:-}" ]]; then
        printf "PROJECT_ID is not set\n\n" >&2
        usage
        exit 1
    fi
    export JIRA_TOKEN
}

install_deps() {
    pip install \
        -r "$PROJECT_DIR/tools/release/dependencies/requirements.txt"
}

run() {
    python3 "$PROJECT_DIR/src/prioritize.py" "$PROJECT_ID" "$FEATURE_ID"
}

main() {
    parse_args "$@"
    install_deps
    run
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    main "$@"
fi
