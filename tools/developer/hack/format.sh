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

Enforce files formatting in the repository.

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

format_python() {
    black "$PROJECT_DIR/src"
    isort \
        --profile "black" \
        "$PROJECT_DIR/src"
}

main() {
    parse_args "$@"
    format_python
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    main "$@"
fi
