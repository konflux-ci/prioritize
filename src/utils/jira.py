import os

import dogpile.cache
import jira

from utils.retry import retry

if os.environ.get("PRIORITIZE_CACHE"):
    cache_args = ("dogpile.cache.dbm",)
    cache_kwargs = dict(
        expiration_time=7200,
        arguments={"filename": "jira.cache"},
    )
else:
    cache_args = ("dogpile.cache.null",)
    cache_kwargs = {}

cache = dogpile.cache.make_region().configure(*cache_args, **cache_kwargs)


def get_issues(
    jira_client: jira.client.JIRA, project_id: str, subquery: str, issue_type: str
) -> list:
    result = query_issues(jira_client, project_id, subquery, issue_type)
    preprocess(jira_client, result)
    return result


def query_issues(
    jira_client: jira.client.JIRA, project_id: str, subquery: str, issue_type: str
) -> dict:
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type} ORDER BY rank ASC"
    if subquery:
        query = f"{subquery} AND {query}"
    results = _search(jira_client, query, verbose=True)
    if not results:
        print(f"No {issue_type} found via query: {query}")
    return results


def get_child_issues(
    jira_client: jira.client.JIRA, project_id: str, subquery: str, issue_type: str
) -> list:
    result = query_child_issues(jira_client, project_id, subquery, issue_type)
    preprocess(jira_client, result)
    return result


def query_child_issues(
    jira_client: jira.client.JIRA, project_id: str, subquery: str, issue_type: str
) -> dict:
    if subquery:
        query = f"issueFunction in portfolioChildrenOf('project={project_id} AND {subquery}')"
    else:
        query = f"issueFunction in portfolioChildrenOf('project={project_id}')"
    query = f"{query} AND resolution=Unresolved AND type={issue_type} ORDER BY rank ASC"
    results = _search(jira_client, query, verbose=True)
    if not results:
        print(f"No {issue_type} found via query: {query}")
    return results


@retry()
def _search(jira_client: jira.client.JIRA, query: str, verbose: bool) -> list:
    @cache.cache_on_arguments()
    def __search(query: str, verbose: bool) -> list:
        if verbose:
            print("  ?", query)

        results = jira_client.search_issues(query, maxResults=0)

        if verbose:
            print("  =", f"{len(results)} results:", [r.key for r in results])
        return results

    return __search(query, verbose)


def preprocess(
    jira_client: jira.client.JIRA, issues: list[jira.resources.Issue]
) -> None:
    fields_ids = get_fields_ids(jira_client, issues)

    for issue in issues:
        issue.raw["Context"] = {}
        issue.raw["Context"]["Field Ids"] = fields_ids
        issue.raw["Context"]["Related Issues"] = {}
        issue.raw["Context"]["Related Issues"]["Parent"] = get_parent(
            jira_client, issue
        )
        issue.raw["Context"]["Related Issues"]["Blocks"] = get_blocks(
            jira_client, issue
        )
        issue.raw["Context"]["Related Issues"]["Children"] = get_children(
            jira_client, issue
        )

    for issue in issues:
        for component in issue.fields.components:
            component.raw["archived"] = is_archived_component(jira_client, component.id)


def is_archived_component(jira_client, component_id):
    @cache.cache_on_arguments()
    def _is_archived_component(component_id):
        return jira_client.component(component_id).archived

    return _is_archived_component(component_id)


def get_fields_ids(
    jira_client: jira.client.JIRA, issues: list[jira.resources.Issue]
) -> dict[str, str]:
    ids = {}
    all_the_fields = jira_client.fields()
    # print(dir(issues[0].fields))
    # debug_fields = '\n'.join(sorted([i['name'] for i in all_the_fields]))
    # print(f"Fields:\n{debug_fields}")

    ids["Rank"] = [f["id"] for f in all_the_fields if f["name"] == "Rank"][0]
    ids["Target Start Date"] = [
        f["id"] for f in all_the_fields if f["name"] == "Target start"
    ][0]
    ids["Target End Date"] = [
        f["id"] for f in all_the_fields if f["name"] == "Target end"
    ][0]
    ids["Due Date"] = [f["id"] for f in all_the_fields if f["name"] == "Due Date"][0]
    ids["RICE Score"] = [f["id"] for f in all_the_fields if f["name"] == "RICE Score"][
        0
    ]

    return ids


def get_parent(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    query = f'issue in parentIssuesOf("{issue.key}") and issue in linksHierarchyIssue("{issue.key}")'
    results = _search(jira_client, query, verbose=False)
    if not results:
        return None
    return results[0]


def get_blocks(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    @retry()
    @cache.cache_on_arguments()
    def _get_blocks(keys):
        blocks = [jira_client.issue(key) for key in keys]
        return blocks

    return _get_blocks(
        [
            il.raw["outwardIssue"]["key"]
            for il in issue.fields.issuelinks
            if il.type.name == "Blocks" and "outwardIssue" in il.raw.keys()
        ]
    )


def get_children(jira_client: jira.client.JIRA, issue: jira.resources.Issue):
    query = f'"Parent Link" = {issue.key} or "Epic Link" = {issue.key}'
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

    @retry()
    def _update():
        issue.update(**data)

    _update()

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
        if has_non_compliant_flag:
            if context["comments"]:
                # If the issue is already marked, don't spam with more comments
                context["comments"].clear()

            if not context["non-compliant"]:
                # If the issue looks good now, then unmark it.
                issue.fields.labels.remove(non_compliant_flag)
                update(issue, {"fields": {"labels": issue.fields.labels}})
                context["comments"].append("  * Issue is now compliant")
        else:
            if context["non-compliant"]:
                issue.fields.labels.append(non_compliant_flag)
                update(issue, {"fields": {"labels": issue.fields.labels}})
