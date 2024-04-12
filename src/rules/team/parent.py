import celpy
import jira

from utils.cel import issue_as_cel


def check_parent_link(
    issue: jira.resources.Issue, context: dict, _: bool, ignore: str = ""
) -> None:
    if ignore:
        env = celpy.Environment()
        program = env.program(env.compile(ignore))
        if program.evaluate(issue_as_cel(issue)):
            context["updates"].append(
                f"! Ignoring {issue.key} for parent link rule, per cel expression: {ignore}."
            )
            return
    if issue.raw["Context"]["Related Issues"]["Parent"] is None:
        context["non-compliant"] = True
        context["comments"].append("  * Issue is missing the link to its parent.")
