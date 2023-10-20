import sys

import jira


def get_issues(jira_client: jira.client.JIRA, project_id: str, issue_type: str) -> list:
    result = query_issues(jira_client, project_id, issue_type)
    preprocess(jira_client, result)
    return result


def query_issues(
    jira_client: jira.client.JIRA, project_id: str, issue_type: str
) -> dict:
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type} ORDER BY rank ASC"
    results = _search(jira_client, query, verbose=True)
    if not results:
        print(f"No {issue_type} found via query: {query}")
        sys.exit(1)
    return results


def get_child_issues(
    jira_client: jira.client.JIRA, project_id: str, issue_type: str
) -> list:
    result = query_child_issues(jira_client, project_id, issue_type)
    preprocess(jira_client, result)
    return result


def query_child_issues(
    jira_client: jira.client.JIRA, project_id: str, issue_type: str
) -> dict:
    query = f"issueFunction in portfolioChildrenOf('project={project_id}') AND resolution=Unresolved AND type={issue_type} ORDER BY rank ASC"
    results = _search(jira_client, query, verbose=True)
    if not results:
        print(f"No {issue_type} found via query: {query}")
        sys.exit(1)
    return results


def _search(jira_client: jira.client.JIRA, query: str, verbose: bool) -> list:
    if verbose:
        print("  ?", query)

    # JIRA can be flaky, so retry a few times before failing
    error = None
    for _ in range(0, 5):
        try:
            results = jira_client.search_issues(query, maxResults=0)
            break
        except jira.exceptions.JIRAError as ex:
            error = ex.text
    else:
        raise RuntimeError(f"'{query}' returned: {error}")

    if verbose:
        print("  =", f"{len(results)} results:", [r.key for r in results])
    return results


def preprocess(
    jira_client: jira.client.JIRA, issues: list[jira.resources.Issue]
) -> None:
    fields_ids = get_fields_ids(jira_client, issues)

    for issue in issues:
        issue.raw["Context"] = {}
        issue.raw["Context"]["Field Ids"] = fields_ids
        issue.raw["Context"]["Related Issues"] = {}
        issue.raw["Context"]["Related Issues"]["Parent"] = get_parent(
            jira_client, issue, fields_ids
        )
        issue.raw["Context"]["Related Issues"]["Blocks"] = get_blocks(
            jira_client, issue
        )
        issue.raw["Context"]["Related Issues"]["Children"] = get_children(
            jira_client, issue
        )


def get_fields_ids(
    jira_client: jira.client.JIRA, issues: list[jira.resources.Issue]
) -> dict[str, str]:
    all_the_fields = jira_client.fields()
    # print(dir(issues[0].fields))
    # debug_fields = '\n'.join(sorted([i['name'] for i in all_the_fields]))
    # print(f"Fields:\n{debug_fields}")
    return dict([(field["name"], field["id"]) for field in all_the_fields])



def get_parent(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    query = f'issue in parentIssuesOf("{issue.key}")'
    results = _search(jira_client, query, verbose=False)
    if not results:
        return None
    return results[0]


def get_blocks(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    blocks = [
        jira_client.issue(il.raw["outwardIssue"]["key"])
        for il in issue.fields.issuelinks
        if il.type.name == "Blocks" and "outwardIssue" in il.raw.keys()
    ]
    return blocks


def get_children(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    query = f'issue in linkedIssues("{issue.key}", "is parent of")'
    return _search(jira_client, query, verbose=False)


def get_version(
    jira_client: jira.client.JIRA, project_key: str, version: str, description: str
):
    versions = jira_client.project_versions(project_key)
    for v in versions:
        if version == v.name:
            return v
    return jira_client.create_version(
        project=project_key, name=version, description=description
    )


def refresh(issue: jira.resources.Issue) -> None:
    update(issue, {})


def update(issue: jira.resources.Issue, data: dict) -> None:
    issue_context = issue.raw.get("Context")

    # JIRA can be flaky, so retry a few times before failing
    for _ in range(0, 5):
        try:
            issue.update(**data)
            break
        except jira.exceptions.JIRAError as e:
            # If the status code is 400, then something is wrong. Likely not a flake.
            if e.status_code == 400:
                raise
            else:
                pass

    # Restore the context that was deleted by the update
    if issue_context:
        issue.raw["Context"] = issue_context


def set_non_compliant_flag(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> None:
    non_compliant_flag = "Non-compliant"
    has_non_compliant_flag = non_compliant_flag in issue.fields.labels
    if context["comments"]:
        print("\n".join(context["comments"]))
    if not dry_run:
        if context["comments"]:
            if has_non_compliant_flag:
                context["comments"].clear()
            else:
                issue.fields.labels.append(non_compliant_flag)
                update(issue, {"fields": {"labels": issue.fields.labels}})
        elif not context["comments"] and has_non_compliant_flag:
            issue.fields.labels.remove(non_compliant_flag)
            update(issue, {"fields": {"labels": issue.fields.labels}})
            context["comments"].append("  * Issue is now compliant")
