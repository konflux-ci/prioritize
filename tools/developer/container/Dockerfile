FROM mcr.microsoft.com/devcontainers/python:3.13

COPY "./tools" "/tmp/tools"

RUN "/tmp/tools/developer/hack/setup_env.sh"

ENV PATH="/workspace/src:/workspace/tools/developer/hack:$PATH"
WORKDIR "/workspace"
ENTRYPOINT "/bin/bash"
