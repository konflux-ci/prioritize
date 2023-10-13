FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

COPY "./tools" "/tmp/tools"

RUN "/tmp/tools/developer/hack/setup_env.sh"

ENV PATH="/workspace/src:/workspace/tools/developer/hack:$PATH"
WORKDIR "/workspace"
ENTRYPOINT "/bin/bash"
