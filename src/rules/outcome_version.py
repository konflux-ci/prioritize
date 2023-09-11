import jira


def set_fix_version(issue: jira.resources.Issue, context: dict, _: bool) -> None:
    parent_issue = issue.raw["Context"]["Related Issues"]["Parent"]
    if parent_issue is None:
        return
    print(parent_issue, dir(parent_issue))
    0/0