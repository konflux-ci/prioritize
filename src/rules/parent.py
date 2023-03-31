import jira


def check_parent_link(issue: jira.resources.Issue, context: dict) -> None:
    if issue.raw["Related Issues"]["Parent"] is None:
        context["comments"].append(f"  * Issue is missing the link to its parent.")
