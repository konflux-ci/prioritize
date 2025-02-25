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
