FROM docker.io/python:3.11

COPY "./tools" "/tmp/tools"

RUN "/tmp/tools/release/hack/setup_env.sh"

WORKDIR "/workspace"
CMD ["/workspace/src/jira_hygiene.py"]
