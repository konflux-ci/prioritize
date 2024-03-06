import jira


def check_parent_link(issue: jira.resources.Issue, context: dict, _: bool) -> None:
    if issue.raw["Context"]["Related Issues"]["Parent"] is None:
        context["non-compliant"] = True
        context["comments"].append("  * Issue is missing the link to its parent.")
