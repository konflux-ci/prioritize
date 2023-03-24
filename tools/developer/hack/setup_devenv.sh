#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR=$(
    cd "$(dirname "$0")" >/dev/null
    pwd
)
PROJECT_DIR=$(
    cd "$SCRIPT_DIR/../../.." >/dev/null
    pwd
)

usage() {
    echo "
Usage:
    ${0##*/} [options]

Setup the development environment.

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

install_deps() {
    pip install \
        -r "$PROJECT_DIR/tools/developer/dependencies/requirements.txt"
    pip install \
        -r "$PROJECT_DIR/tools/release/dependencies/requirements.txt"
}

main() {
    parse_args "$@"
    install_deps
}

if [ "${BASH_SOURCE[0]}" == "$0" ]; then
    main "$@"
fi
