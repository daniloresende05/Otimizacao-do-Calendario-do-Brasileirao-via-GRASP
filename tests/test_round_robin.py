from brasileirao.round_robin import circle_method

def test_circle_method_20_teams_has_19_rounds():
    teams = [f"T{i}" for i in range(20)]
    rounds = circle_method(teams)
    assert len(rounds) == 19
    assert all(len(r) == 10 for r in rounds)
