import operator as op

import rules.team.timesensitive_rank


def test_rank_idempotence(issues):
    issues = list(sorted(issues.values(), key=op.attrgetter("fields.rank")))
    issues = [issue for issue in issues if issue.key not in ("child0", "child4")]
    blocks = rules.team.timesensitive_rank.Blocks(issues)
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    assert new_ranking == old_ranking


def test_rank_single_move(issues):
    issues["child3"].raw["Context"]["Related Issues"]["Parent"].fields.rank = -1
    blocks = rules.team.timesensitive_rank.Blocks(list(issues.values()))
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    assert new_ranking != old_ranking
    assert new_ranking[0].key == "child3"
    assert new_ranking[1].key == "child1"
    assert new_ranking[2].key == "child2"
    # Highly ranked orphan child is not maintained
    assert new_ranking[3].key == "child0"
    assert new_ranking[4].key == "child4"


def test_rank_with_dates(issues_with_due_dates):
    issues = issues_with_due_dates
    issues["child3"].raw["Context"]["Related Issues"]["Parent"].fields.rank = -1
    blocks = rules.team.timesensitive_rank.Blocks(list(issues.values()))
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    import pprint

    pprint.pprint(new_ranking)
    assert new_ranking != old_ranking
    assert new_ranking[0].key == "child5"
    assert new_ranking[1].key == "child4"
    assert new_ranking[2].key == "child2"
    assert new_ranking[3].key == "child3"
    assert new_ranking[4].key == "child1"


def test_rank_with_priorities(issues_with_priorities):
    issues = list(issues_with_priorities.values())
    blocks = rules.team.timesensitive_rank.Blocks(issues)
    blocks.sort()
    new_ranking = blocks.get_issues()
    expected = [
        "child6",
        "child5",
        "child7",
        "child8",
        "child9",
        "child2",
        "child4",
        "child3",
        "child1",
        "child0",
    ]
    actual = [issue.key for issue in new_ranking]
    assert actual == expected
