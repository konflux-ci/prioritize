import operator as op
from time import strftime

import celpy
import jira

from utils.cel import issue_as_cel
from utils.jira import update

today = strftime("%Y-%m-%d")


def _earliest_fixversion(issue):
    fixversions = issue.fields.fixVersions
    if not fixversions:
        return None
    fixversions = [
        fixversion for fixversion in fixversions if hasattr(fixversion, "releaseDate")
    ]
    if not fixversions:
        return None
    return sorted(fixversions, key=op.attrgetter("releaseDate"))[0]


def check_due_date_by_fixversion(
    issue: jira.resources.Issue, context: dict, dry_run: bool, ignore: str = ""
) -> None:
    if ignore:
        env = celpy.Environment()
        program = env.program(env.compile(ignore))
        if program.evaluate(issue_as_cel(issue)):
            context["updates"].append(
                f"! Ignoring {issue.key} for due date by fixVersion rule, per cel expression: {ignore}."
            )
            return

    fixversion = _earliest_fixversion(issue)
    if not fixversion:
        return

    target_due_date = fixversion.releaseDate
    target_source = fixversion

    if target_due_date is None:
        raise ValueError(
            "Impossible - fixversion due date cannot be None at this location"
        )

    due_date_id = issue.raw["Context"]["Field Ids"]["Due Date"]
    due_date = getattr(issue.fields, due_date_id)

    if not due_date or due_date > target_due_date:
        if not due_date:
            message = f"  * Setting Due Date to {target_due_date}, inherited from fixVersion {target_source.name}."
        elif due_date > target_due_date:
            message = f"  * Pulling in Due Date from {due_date} to {target_due_date}, propagated from fixVersion {target_source.name}."

        context["updates"].append(message)
        context["comments"].append(message)

        if not dry_run:
            update(issue, {"fields": {due_date_id: target_due_date}})
