"""
JIRA Issue Status Automation Based on Child Issue Hierarchy.

This module provides functionality to automatically update parent JIRA issue statuses
based on the collective status of their child issues. It implements a bottom-up
hierarchical status propagation system that ensures parent issues accurately reflect
the progress of their child work items.

Key Features:
    - Recursive status processing for multi-level issue hierarchies
    - Automatic status category mapping and transitions
    - Dry-run support for safe testing and validation
    - Comprehensive logging of all status changes

Status Logic:
    The module applies the following business rules for parent status determination:

    - **To Do**: All child issues are in "To Do" status category
    - **Done**: All child issues are in "Done" status category
    - **In Progress**: Any mixed combination of child statuses, or any child
      is actively being worked on

Status Mappings:
    Status categories are mapped to specific JIRA statuses during transitions:

    - "To Do" → "New"
    - "In Progress" → "In Progress"
    - "Done" → "Closed"

Note:
    The module handles arbitrarily deep hierarchies by recursively processing
    each level from bottom to top, ensuring that all status updates propagate
    correctly through the entire issue tree.
"""

import jira

from utils.jira import get_children


def set_status_from_children(
    issue: jira.resources.Issue,
    context: dict,
    dry_run: bool,
) -> str:
    """Compute and update the status of the issue based on its children's statuses.

    This function recursively processes an issue and its children to determine
    the appropriate status category. The status is updated based on the collective
    status of all child issues:
    - If all children are "To Do", parent becomes "To Do"
    - If all children are "Done", parent becomes "Done"
    - If children have mixed statuses, parent becomes "In Progress"

    Args:
        issue (jira.resources.Issue): The JIRA issue to process
        context (dict): Context dictionary containing 'jira_client' and 'updates' keys
        dry_run (bool): If True, only simulate the update without making actual changes

    Returns:
        str: The status category name after processing ("To Do", "In Progress", or "Done")
    """
    statusCategories = _get_children_status_categories(issue, context, dry_run)
    if not statusCategories:
        return issue.get_field("status").statusCategory.name

    new_status_category = _get_updated_status(statusCategories)
    if new_status_category != issue.get_field("status").statusCategory.name:
        _update_status(issue, new_status_category, context, dry_run)

    return new_status_category


def _get_children_status_categories(
    issue: jira.resources.Issue, context: dict, dry_run: bool
) -> set[str]:
    """Recursively collect status categories from all child issues.

    This function retrieves all direct children of the given issue and
    recursively processes each child to get their final status categories.
    This ensures that multi-level hierarchies are properly handled.

    Args:
        issue (jira.resources.Issue): The parent issue whose children to process
        context (dict): Context dictionary containing JIRA client and updates list
        dry_run (bool): If True, simulate updates without making actual changes

    Returns:
        set[str]: A set of unique status category names from all child issues
    """
    statusCategories = set()
    children = get_children(context["jira_client"], issue)
    for child in children:
        status = set_status_from_children(child, context, dry_run)
        statusCategories.add(status)
    return statusCategories


def _get_updated_status(statusCategories: set[str]) -> str:
    """Determine the appropriate parent status based on children's status categories.

    Applies business logic to determine parent issue status:
    - If all children are "To Do": parent should be "To Do"
    - If all children are "Done": parent should be "Done"
    - Any other combination (mixed or "In Progress"): parent should be "In Progress"

    Args:
        statusCategories (set[str]): Set of status category names from child issues

    Returns:
        str: The appropriate status category for the parent issue
    """
    # No issue has been worked on yet, set to New
    if statusCategories == {"To Do"}:
        return "To Do"
    # All issues have been done, set to Closed
    if statusCategories == {"Done"}:
        return "Done"
    return "In Progress"


def _update_status(
    issue: jira.resources.Issue,
    new_status_category: str,
    context: dict,
    dry_run: bool,
) -> None:
    """Update the JIRA issue status to match the new status category.

    Maps status categories to specific JIRA statuses and performs the transition:
    - "To Do" -> "New" status
    - "In Progress" -> "In Progress" status
    - "Done" -> "Closed" status

    The function logs the update action and, if not in dry-run mode, performs
    the actual JIRA status transition.

    Args:
        issue (jira.resources.Issue): The JIRA issue to update
        new_status_category (str): Target status category ("To Do", "In Progress", "Done")
        context (dict): Context dictionary with 'jira_client' and 'updates' keys
        dry_run (bool): If True, only log the intended change without executing it

    Returns:
        None

    Side Effects:
        - Appends update message to context['updates'] list
        - If not dry_run, transitions the issue status in JIRA
        - Prints error message if transition is not available
    """
    update = {
        "To Do": {"msg": "Work on child issues has not started.", "status": "New"},
        "In Progress": {
            "msg": "Work on child issues is on-going.",
            "status": "In Progress",
        },
        "Done": {"msg": "All child issues have been closed.", "status": "Closed"},
    }[new_status_category]

    if dry_run:
        msg = f"  * Updating Status of {issue.key} to '{update['status']}': {update['msg']}"
    else:
        msg = f"  * Updating Status to '{update['status']}': {update['msg']}"
    context["updates"].append(msg)

    if not dry_run:
        jira_client = context["jira_client"]
        transitions = jira_client.transitions(issue)
        transition_id = next(
            (t["id"] for t in transitions if t["name"] == update["status"]), None
        )
        if transition_id:
            jira_client.transition_issue(issue.key, transition_id)
        else:
            print(f"!!! No '{update['status']}' transition found for {issue.key}")
