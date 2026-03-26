import difflib
import os

import dogpile.cache
from atlassian import Jira

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
    jira_client: Jira,
    project_id: str,
    subquery: str,
    issue_type: str,
    order_by: str = "rank ASC",
    verbose: bool = True,
) -> list:
    result = query_issues(
        jira_client, project_id, subquery, issue_type, order_by, verbose
    )
    preprocess(jira_client, result)
    return result


def query_issues(
    jira_client: Jira,
    project_id: str,
    subquery: str,
    issue_type: str,
    order_by: str,
    verbose: bool = True,
) -> list:
    query = f"project={project_id} AND resolution=Unresolved AND type={issue_type}"
    if subquery:
        query += f" AND {subquery}"
    if order_by:
        query += f" ORDER BY {order_by}"
    results = _search(jira_client, query, verbose)
    if not results:
        print(f"No {issue_type} found via query: {query}")
    return results


def get_child_issues(
    jira_client: Jira, project_id: str, subquery: str, issue_type: str
) -> list:
    result = query_child_issues(jira_client, project_id, subquery, issue_type)
    preprocess(jira_client, result)
    return result


def query_child_issues(
    jira_client: Jira, project_id: str, subquery: str, issue_type: str
) -> list:
    parent_filter = f"project={project_id}"
    if subquery:
        parent_filter += f" AND {subquery}"
    query = f"parent in ({parent_filter}) AND resolution=Unresolved AND type={issue_type} ORDER BY rank ASC"
    results = _search(jira_client, query, verbose=True)
    if not results:
        print(f"No {issue_type} found via query: {query}")
    return results


@retry()
def _search(jira_client: Jira, query: str, verbose: bool) -> list:
    @cache.cache_on_arguments()
    def __search(query: str, verbose: bool) -> list:
        if verbose:
            print("  ?", query)

        results: list = []
        next_page_token: str | None = None
        while True:
            response = jira_client.enhanced_jql(
                query, nextPageToken=next_page_token
            )  # , expand='renderedFields'
            if not response:
                break
            results.extend(response.get("issues", []))
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        if verbose:
            print("  =", f"{len(results)} results:", [r["key"] for r in results])
        return results

    return __search(query, verbose)


def preprocess(
    jira_client: Jira, issues: list[dict], parent: dict | None = None
) -> None:
    fields_ids = get_fields_ids(jira_client)

    for issue in issues:
        if "Context" not in issue:
            issue["Context"] = {}
        issue["_jira_client"] = jira_client
        issue["Context"]["Field Ids"] = fields_ids
        issue["Context"]["Related Issues"] = {}
        if parent:
            issue["Context"]["Related Issues"]["Parent"] = parent
            return
        issue["Context"]["Related Issues"]["Parent"] = get_parent(jira_client, issue)
        issue["Context"]["Related Issues"]["Blocks"] = get_blocks(jira_client, issue)
        issue["Context"]["Related Issues"]["Children"] = get_children(
            jira_client, issue
        )


def is_archived_component(jira_client, component_id):
    @retry()
    @cache.cache_on_arguments()
    def _is_archived_component(component_id):
        return jira_client.component(component_id).archived

    return _is_archived_component(component_id)


def get_fields_ids(jira_client: Jira) -> dict[str, str]:
    ids = {}
    all_the_fields = jira_client.get_all_fields()
    # print(dir(issues[0].fields))
    # debug_fields = "\n".join(sorted([i["name"] for i in all_the_fields]))
    # print(f"Fields:\n{debug_fields}")

    mapping = {
        "Rank": "Rank",
        "Target start": "Target Start Date",
        "Target end": "Target End Date",
        "Due date": "Due Date",
        "RICE Score": "RICE Score",
        "Parent": "Parent",
    }
    for name, id in mapping.items():
        ids[id] = [f["id"] for f in all_the_fields if f["name"] == name][0]

    return ids


def get_parent(jira_client: Jira, issue: dict) -> dict | None:
    parent = None
    if "parent" in issue["fields"].keys():
        parent = jira_client.get_issue(issue["fields"]["parent"]["key"])
        preprocess(jira_client, [parent])
    return parent


def get_blocks(jira_client: Jira, issue: dict) -> list[dict]:
    """
    Get issues blocked by an issue.
    """

    @retry()
    @cache.cache_on_arguments()
    def _get_blocks(keys):
        blocks = [jira_client.issue(key) for key in keys]
        return blocks

    blocked_issue_keys = []
    for il in issue["fields"]["issuelinks"]:
        if il["type"]["name"] == "Blocks" and "outwardIssue" in il:
            blocked_issue_keys.append(il["outwardIssue"]["key"])
    blocked_issues = _get_blocks(blocked_issue_keys)
    return blocked_issues


def get_children(jira_client: Jira, issue: dict, order_by: str = ""):
    query = f'Parent = {issue["key"]}'
    if order_by:
        query += f" ORDER BY {order_by}"
    children = _search(jira_client, query, verbose=False)
    preprocess(jira_client, children, parent=issue)
    return children


def get_version(jira_client: Jira, project: dict, version: str):
    versions = jira_client.get_project_versions(project["key"])
    for v in versions:
        if version == v["name"]:
            return v
    v = jira_client.add_version(
        project_key=project["key"], project_id=project["id"], version=version
    )
    return v


def refresh(issue: dict) -> None:
    update(issue, {})


def update(issue: dict, data: dict) -> None:
    jira_client = issue.get("_jira_client")
    if not jira_client:
        raise ValueError("jira_client not found in issue. Issue must be preprocessed.")

    @retry()
    def _update():
        jira_client.edit_issue(issue_id_or_key=issue["key"], fields=data)

    _update()


def set_non_compliant_flag(issue: dict, context: dict, dry_run: bool) -> None:
    non_compliant_flag = "Non-compliant"
    labels = issue["fields"]["labels"]
    has_non_compliant_flag = non_compliant_flag in labels
    if not dry_run:
        if has_non_compliant_flag:
            if context["comments"]:
                # If the issue is already marked, don't spam with more comments
                context["comments"].clear()
            if not context["non-compliant"]:
                # If the issue looks good now, then unmark it.
                update(issue, {"labels": [{"remove": non_compliant_flag}]})
                context["comments"].append("  * Issue is now compliant")
                labels.remove(non_compliant_flag)
        else:
            if context["non-compliant"]:
                update(issue, {"labels": [{"add": non_compliant_flag}]})
                context["comments"].append("  * Issue is now non-compliant")
                labels.append(non_compliant_flag)


def rank_issues(
    new_ranking: list[dict], old_ranking: list[dict], dry_run: bool
) -> None:
    jira_client = new_ranking[0]["_jira_client"]
    print(f"\n### Reranking issues ({__name__})")
    previous_issue = None
    total = len(new_ranking)
    rerank = False
    rank_field_id = int(old_ranking[0]["Context"]["Field Ids"]["Rank"].split("_")[1])

    print(
        "".join(
            list(
                difflib.unified_diff(
                    [
                        f"{issue['key']} {issue['fields']['summary']}\n"
                        for issue in old_ranking
                    ],
                    [
                        f"{issue['key']} {issue['fields']['summary']}\n"
                        for issue in new_ranking
                    ],
                    "old_ranking",
                    "new_ranking",
                )
            )
        )
    )

    # Start from the bottom of the ranking and work our way up.
    # This is because the rank_update method can only move issues up.
    for index, issues in enumerate(zip(reversed(old_ranking), reversed(new_ranking))):
        old_issue, new_issue = issues
        if new_issue != old_issue:
            # Once we start reranking, we don't stop.
            # This should avoid any edge case, but it's slow.
            rerank = True
        if rerank and previous_issue is not None:
            if dry_run:
                print(
                    f"  > {new_issue['key']} would be moved just above {previous_issue['key']}"
                )
            else:
                jira_client.update_rank(
                    issues_to_rank=[new_issue["key"]],
                    rank_before=previous_issue["key"],
                    customfield_number=rank_field_id,
                )
        elif dry_run:
            print(f"  > {new_issue['key']} is already in the right place")

        previous_issue = new_issue
        print(f"\r{100 * (index + 1) // total}%", end="", flush=True)
