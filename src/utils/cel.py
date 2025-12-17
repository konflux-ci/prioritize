import celpy


def issue_as_cel(issue: dict):
    return dict(
        key=issue["key"],
        labels=celpy.json_to_cel(issue["fields"]["labels"]),
        components=celpy.json_to_cel(
            [component["name"] for component in issue["fields"]["components"]]
        ),
    )
