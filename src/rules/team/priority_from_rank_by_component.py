"""
Set priority on issues based on the feature rank, split by component.

Highly ranked features for any component are critical, the lowest ranked features are minor

"""

import operator as op

import jira

from utils.jira import update


def check_priority_from_rank_by_component(
    issues: list[jira.resources.Issue],
    context: dict,
    dry_run: bool,
) -> None:
    """Set priority based on rank"""
    jira_client = context["jira_client"]
    footer = context["footer"]

    components = Components.from_issues(issues)
    for issue in issues:
        relevant = Components.from_subset(
            [component for component in components if issue in component]
        )
        _set_priority(
            jira_client,
            issue,
            relevant.priority(issue),
            relevant.message(issue),
            footer,
            dry_run,
        )


def _set_priority(
    jira_client: jira.client.JIRA,
    issue: jira.resources.Issue,
    priority: str,
    message: str,
    footer: str,
    dry_run: bool,
) -> None:

    if issue.fields.priority.name == priority:
        return

    print(message)
    if not dry_run:
        update(issue, {"priority": {"name": priority}})
        if footer:
            message = f"{message}\n\n{footer}"
        jira_client.add_comment(issue.key, message)


class Assessment:
    def __init__(self, component, index, total):
        self.component = component
        self.index = index
        self.total = total
        self.percentile = index / total


class Components:
    def __init__(self):
        self.components = {}

    @classmethod
    def from_issues(cls, issues):
        self = Components()
        for issue in issues:
            for component in issue.fields.components:
                if component.name not in self.components:
                    self.components[component.name] = Component(name=component.name)
                component = self.components[component.name]
                component.add(issue)
        return self

    @classmethod
    def from_subset(cls, components):
        self = Components()
        self.components = {component.name: component for component in components}
        return self

    def __iter__(self):
        yield from self.components.values()

    def assess(self, issue):
        for component in self:
            yield Assessment(component, component.index(issue), len(component))

    def message(self, issue):
        assessments = self.assess(issue)
        assessments = sorted(assessments, key=op.attrgetter("percentile"))
        try:
            leader = assessments[0]
        except IndexError:
            return (
                f"Updating priority from {issue.fields.priority} to Undefined to reflect "
                f"the fact that {issue.key} currently has no components set."
            )

        message = (
            f"Updating priority from {issue.fields.priority} to {self.priority(issue)} to reflect "
            f"{issue.key}'s current rank in the {leader.component.name} backlog, position {leader.index + 1} "
            f"of {leader.total}."
        )
        if len(assessments) > 1:
            message += f" ({issue.key} is also ranked "
            message += ", ".join(
                f"{assessment.index + 1} out of {assessment.total} for {assessment.component.name}"
                for assessment in assessments[1:]
            )
            message += ")"
        return message

    def priority(self, issue):
        assessments = self.assess(issue)
        try:
            leader = sorted(assessments, key=op.attrgetter("percentile"))[0]
        except IndexError:
            return "Undefined"

        priorities = [
            ("Critical", 0.0625),
            ("Major", 0.125),
            ("Normal", 0.25),
            ("Minor", 1),
        ]

        for priority, threshold in priorities:
            if leader.percentile <= threshold:
                return priority

        raise ValueError("How did we get here?")


class Component:
    def __init__(self, name):
        self.name = name
        self.issues = []

    def __len__(self):
        return len(self.issues)

    def __contains__(self, issue):
        return issue in self.issues

    def add(self, issue):
        self.issues.append(issue)

    def index(self, issue):
        return self.issues.index(issue)
