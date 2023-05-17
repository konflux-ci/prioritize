FROM python:3.11

COPY "." "/tmp/tools"

RUN "/tmp/tools/developer/hack/setup_env.sh" \
    && mkdir "/workspace"

ENV PATH="/workspace/src:/workspace/tools/developer/hack:$PATH"
WORKDIR "/workspace"
ENTRYPOINT "/bin/bash"
