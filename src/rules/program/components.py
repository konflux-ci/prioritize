import jira

from utils.jira import update


def check_components(issue: jira.resources.Issue, context: dict, dry_run: bool) -> None:
    children = issue.raw["Context"]["Related Issues"]["Children"]

    # Do not update components if there are no children.
    # In that case the components should be viewed as the expected impact of the issue.
    if not children:
        return

    child_components = set(sum([i.fields.components for i in children], []))
    child_components = [c.name for c in child_components]
    child_components.sort()

    components = issue.fields.components
    components = [c.name for c in components]
    components.sort()

    to_add = set(child_components) - set(components)
    to_remove = set(components) - set(child_components)

    if to_add:
        context["updates"].append(f"  > Adding components {to_add}.")
    if to_remove:
        context["updates"].append(f"  > Removing components {to_remove}.")

    if not dry_run and (to_add or to_remove):
        update(
            issue,
            data=dict(
                update={
                    "components": [{"set": [{"name": c} for c in child_components]}]
                }
            ),
        )
