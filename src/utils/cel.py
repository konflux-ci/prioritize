import celpy
import jira


def issue_as_cel(issue: jira.resources.Issue):
    return dict(
        key=issue.key,
        labels=celpy.json_to_cel([label for label in issue.fields.labels]),
        components=celpy.json_to_cel(
            [component.name for component in issue.fields.components]
        ),
    )
