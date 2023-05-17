FROM python:3.11

COPY "." "/tmp/tools/release"

RUN "/tmp/tools/release/hack/setup_env.sh" \
    && mkdir "/workspace"

WORKDIR "/workspace"
CMD ["/workspace/src/prioritize-stories.py"]
