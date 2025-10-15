FROM quay.io/fedora/python-313:latest

COPY "./tools" "/tmp/tools"

RUN "/tmp/tools/release/hack/setup_env.sh"

WORKDIR "/workspace"
CMD ["/workspace/src/jira_hygiene.py"]
