#!/bin/env bash
./tools/release/hack/run.sh -- -p PLNSRVCE -t $(cat ~/.config/tokens/jira/rarnaud@redhat.com) "$@"
