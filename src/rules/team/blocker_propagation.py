"""
When a child issue gains or loses a "is blocked by" link, the next bot run adds or removes the
corresponding link on the parent issue so parents reflect rollup state.
"""

from __future__ import annotations

import os
from typing import Any, Collection

from atlassian import Jira

from utils.jira import get_descendant_issues


def _is_blocked_by_link_type(link_type: dict | None) -> bool:
    """
    Detect issue links where the *inward* issue "is blocked by" the *outward* issue.
    """
    if not link_type:
        return False
    name = (link_type.get("name") or "").lower()
    if name in ("blocks", "blockers"):
        return True
    inward = (link_type.get("inward") or "").lower()
    if "blocked" in inward and "by" in inward:
        return True
    return False


def _blocking_issue_keys(issue: dict) -> list[str]:
    """
    Keys of issues that *block* ``issue`` (i.e. ``issue`` is blocked by them).
    """
    keys: list[str] = []
    my_key = issue["key"]
    for il in issue["fields"].get("issuelinks", []) or []:
        if not _is_blocked_by_link_type(il.get("type")):
            continue
        inward_key = (il.get("inwardIssue") or {}).get("key")
        if inward_key and inward_key != my_key:
            keys.append(inward_key)
    return keys


def _inward_blocks_entries(issue: dict) -> list[tuple[str, str]]:
    """(blocker_key, link_id) for blocked-by links on this issue."""
    out: list[tuple[str, str]] = []
    my_key = issue["key"]
    for il in issue["fields"].get("issuelinks", []) or []:
        if not _is_blocked_by_link_type(il.get("type")):
            continue
        inward_key = (il.get("inwardIssue") or {}).get("key")
        if inward_key and inward_key != my_key:
            lid = il.get("id")
            if lid is not None:
                out.append((inward_key, str(lid)))
    return out


_BATCH_SIZE = 50


def _batch_merge_issuelinks(jira_client: Jira, issues: list[dict]) -> None:
    """Fetch issuelinks for many issues in batched JQL queries."""
    if not issues:
        return
    by_key = {}
    for iss in issues:
        by_key[iss["key"]] = iss

    keys = list(by_key.keys())
    for offset in range(0, len(keys), _BATCH_SIZE):
        batch = keys[offset : offset + _BATCH_SIZE]  # noqa: E203
        jql = f'key in ({",".join(batch)})'
        next_page_token: str | None = None
        while True:
            response = jira_client.enhanced_jql(
                jql, fields=["issuelinks"], nextPageToken=next_page_token
            )
            if not response:
                break
            for result in response.get("issues", []):
                key = result.get("key")
                if key and key in by_key:
                    fields = result.get("fields") or {}
                    by_key[key].setdefault("fields", {})
                    if "issuelinks" in fields:
                        by_key[key]["fields"]["issuelinks"] = fields["issuelinks"] or []
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break


def sync_blocker_links_from_descendants(
    issue: dict,
    context: dict,
    dry_run: bool,
    container_issue_types: Collection[str] | None = None,
    link_type_name: str = "Blocks",
    **_: Any,
) -> None:
    """
    For an Epic or Feature, set "is blocked by" to exactly the union of blockers on
    all descendant issues (any issue type under the Parent hierarchy), adding and
    removing Issue Links as needed.
    """
    if container_issue_types is None:
        container_issue_types = ("Epic", "Feature")

    itype = (issue["fields"].get("issuetype") or {}).get("name")
    if itype not in container_issue_types:
        return

    jira_client: Jira = context["jira_client"]
    descendants = get_descendant_issues(jira_client, issue["key"], unresolved_only=True)
    if not descendants:
        if os.environ.get("PRIORITIZE_BLOCKER_DIAG"):
            context["updates"].append(
                f"  * Blocker sync: 0 descendants for {issue['key']} "
                "(JQL: Parent/parent/Epic Link). Child must use one of these to the Epic."
            )
        return

    _batch_merge_issuelinks(jira_client, [issue, *descendants])

    desired: set[str] = set()
    for d in descendants:
        desired |= set(_blocking_issue_keys(d))

    my_key = issue["key"]
    entries = _inward_blocks_entries(issue)
    current_by_blocker = {b: lid for b, lid in entries}

    to_add = sorted(desired - current_by_blocker.keys())
    to_remove = sorted(current_by_blocker.keys() - desired)

    if (
        os.environ.get("PRIORITIZE_BLOCKER_DIAG")
        and dry_run
        and not to_add
        and not to_remove
    ):
        context["updates"].append(
            f"  * Blocker sync: {len(descendants)} descendant(s); "
            "union of inward Blocks on descendants matches Epic (nothing to change)."
        )
    if os.environ.get("PRIORITIZE_BLOCKER_DIAG") == "2":
        desc_keys = sorted(d["key"] for d in descendants)
        context["updates"].append(
            f"  * Blocker sync DEBUG: descendant_keys={desc_keys} "
            f"desired_blockers={sorted(desired)} "
            f"epic_inward_blockers={sorted(current_by_blocker.keys())} "
            f"to_add={to_add} to_remove={to_remove}"
        )

    for blocker in to_add:
        if blocker == my_key:
            continue
        # Jira Cloud create: inwardIssue=blocker, outwardIssue=blocked party
        payload = {
            "type": {"name": link_type_name},
            "inwardIssue": {"key": blocker},
            "outwardIssue": {"key": my_key},
        }
        msg = f"  * Add link: {my_key} is blocked by {blocker}"
        if dry_run:
            context["updates"].append(f"{msg} [dry-run, not created]")
        else:
            jira_client.create_issue_link(payload)
            context["updates"].append(f"{msg} [created]")

    for blocker in to_remove:
        link_id = current_by_blocker[blocker]
        msg = f"  * Remove link: {my_key} is blocked by {blocker}"
        if dry_run:
            context["updates"].append(f"{msg} [dry-run, not removed]")
        else:
            jira_client.remove_issue_link(link_id)
            context["updates"].append(f"{msg} [removed]")
