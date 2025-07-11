import operator as op

import rules.team.timesensitive_rank


def test_base_sorting(issues_with_due_dates):
    issue_list = list(
        sorted(issues_with_due_dates.values(), key=op.attrgetter("fields.rank"))
    )
    blocks = rules.team.timesensitive_rank.Blocks(issue_list)
    new_ranking = blocks.get_issues()

    # child5 has the earliest due date, so it should be first.
    # child4 has the second earliest, so it should be second.
    assert new_ranking[0].key == "child5"
    assert new_ranking[1].key == "child4"

    # Verify block placement
    due_date_block = blocks.blocks[0]
    inert_block = blocks.blocks[1]
    rice_block = blocks.blocks[2]

    assert issues_with_due_dates["child5"] in due_date_block.issues
    assert issues_with_due_dates["child4"] in due_date_block.issues
    assert issues_with_due_dates["child3"] in inert_block.issues
    assert issues_with_due_dates["child2"] in inert_block.issues
    assert issues_with_due_dates["child1"] in inert_block.issues
    assert issues_with_due_dates["child6"] in rice_block.issues


def test_rank_idempotence(issues):
    issues = list(sorted(issues.values(), key=op.attrgetter("fields.rank")))
    issues = [issue for issue in issues if issue.key not in ("child0", "child4")]
    blocks = rules.team.timesensitive_rank.Blocks(issues)
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    assert new_ranking == old_ranking


def test_rank_manual_override(issues):
    # The "child1" issue has a due date, so it would normally be in the DueDateBlock.
    # The manual_override should force it into the InertBlock.
    issue_list = list(sorted(issues.values(), key=op.attrgetter("fields.rank")))
    blocks = rules.team.timesensitive_rank.Blocks(
        issue_list, manual_override="key == 'child1'"
    )
    assert issues["child1"] in blocks.blocks[1].issues


def test_rank_manual_override_component(issues):
    # The "child2" issue has a due date, so it would normally be in the DueDateBlock.
    # The manual_override should force it into the InertBlock because of its component.
    issue_list = list(sorted(issues.values(), key=op.attrgetter("fields.rank")))
    blocks = rules.team.timesensitive_rank.Blocks(
        issue_list, manual_override="components.exists(c, c in ['Component2'])"
    )
    assert issues["child2"] in blocks.blocks[1].issues
