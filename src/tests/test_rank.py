import rules.team.rank


def test_rank_idempotence(issues):
    blocks = rules.team.rank.Blocks(list(issues.values()))
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    assert new_ranking == old_ranking


def test_rank_single_move(issues):
    issues["child3"].raw["Context"]["Related Issues"]["Parent"].fields.rank = 0
    blocks = rules.team.rank.Blocks(list(issues.values()))
    old_ranking = blocks.get_issues()
    blocks.sort()
    new_ranking = blocks.get_issues()
    assert new_ranking != old_ranking
    assert new_ranking[0].key == "child0"  # Highly ranked orphan child is maintained
    assert new_ranking[1].key == "parent3"
    assert new_ranking[2].key == "child3"
    assert new_ranking[3].key == "parent1"
    assert new_ranking[4].key == "child1"
    assert new_ranking[5].key == "parent2"
    assert new_ranking[6].key == "child2"
