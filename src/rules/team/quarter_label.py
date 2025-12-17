from re import compile

from utils.jira import update


def check_quarter_label(issue: dict, context: dict, dry_run: bool) -> None:
    parent_issue = issue["Context"]["Related Issues"]["Parent"]
    if parent_issue is None:
        return

    re_quarter = compile("[0-9]{4}Q[1-4]")
    parent_labels = parent_issue["fields"]["labels"]
    issue_labels = issue["fields"]["labels"]
    for label in parent_labels:
        if re_quarter.match(label) and label not in issue_labels:
            context["updates"].append(f"  > Adding label: {label}.")
            if not dry_run:
                issue_labels.append(label)
                update(issue, {"labels": [{"add": label}]})
    for label in issue_labels:
        if re_quarter.match(label) and label not in parent_labels:
            context["updates"].append(f"  < Removing label: {label}.")
            if not dry_run:
                issue_labels.remove(label)
                update(issue, {"labels": [{"remove": label}]})
