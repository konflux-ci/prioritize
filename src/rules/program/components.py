"""
Check if the components of an issue are consistent with the components of its children.

If the issue does not have children, then it is not modified. Components are expected to represent the expected impact of the issue.
If the issue has children, then the components are set to the union of its children's components.
"""

from utils.jira import update


def check_components(issue: dict, context: dict, dry_run: bool) -> None:
    children = issue["Context"]["Related Issues"]["Children"]

    # Do not update components if there are no children.
    # In that case the components should be viewed as the expected impact of the issue.
    if not children:
        return

    child_components = set()
    for i in children:
        child_components.update([c["name"] for c in i["fields"]["components"]])

    components = set([c["name"] for c in issue["fields"]["components"]])

    to_add = child_components - components
    to_remove = components - child_components

    data = []
    if to_add:
        context["updates"].append(f"  > Adding components {to_add}.")
        data += [{"add": {"name": component}} for component in to_add]
    if to_remove:
        context["updates"].append(f"  > Removing components {to_remove}.")
        data += [{"remove": {"name": component}} for component in to_remove]
    if data and not dry_run:
        update(issue, {"components": data})
