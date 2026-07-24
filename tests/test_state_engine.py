from cs2mc.state_engine import GameStateResolver


def payload(*, activity="playing", phase="live", health=100, bomb="", kills=0, round_no=4, observed=False):
    provider_id = "111"
    player_id = "222" if observed else provider_id
    result = {
        "provider": {"appid": 730, "steamid": provider_id},
        "map": {"round": round_no, "phase": "live"},
        "player": {
            "steamid": player_id,
            "activity": activity,
            "state": {"health": health, "round_kills": kills},
        },
        "round": {"phase": phase},
    }
    if bomb:
        result["round"]["bomb"] = bomb
    return result


def test_required_game_states():
    resolver = GameStateResolver()
    assert resolver.process(payload(activity="menu")).state == "menu"
    assert resolver.process(payload(phase="freezetime")).state == "buy_phase"
    assert resolver.process(payload()).state == "game"
    assert resolver.process(payload(observed=True)).state == "spectating"
    assert resolver.process(payload(bomb="planted")).state == "bomb_planted"


def test_kill_streak_increments_and_resets_by_round():
    resolver = GameStateResolver()
    assert resolver.process(payload(kills=0, round_no=1)).kill_streak is None
    assert resolver.process(payload(kills=1, round_no=1)).kill_streak == 1
    assert resolver.process(payload(kills=2, round_no=1)).kill_streak == 2
    next_round = resolver.process(payload(kills=0, round_no=2))
    assert next_round.kill_streak is None
    assert resolver.process(payload(kills=1, round_no=2)).kill_streak == 1


def test_ignores_non_cs2_payloads():
    resolver = GameStateResolver()
    assert resolver.process({"provider": {"appid": 999}}) is None
