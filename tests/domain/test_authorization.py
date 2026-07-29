import pytest
from ti_dash.domain.game import Game


def test_add_player_assigns_sequential_seats():
    g = Game()
    a = g.add_player("Ana", "F", "Red")
    b = g.add_player("Bo", "F", "Blue")
    assert (a.seat, b.seat) == (0, 1)


def test_claim_and_authorize_owner():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "dev-1")
    assert p.claim_token == "dev-1"
    g.authorize(p, "dev-1", is_admin=False)  # no raise


def test_claim_conflict_raises():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "dev-1")
    with pytest.raises(PermissionError):
        g.claim_seat(p, "dev-2")


def test_reclaim_by_same_device_is_allowed():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "dev-1")
    g.claim_seat(p, "dev-1")  # idempotent, no raise


def test_non_owner_authorize_raises_but_admin_passes():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "dev-1")
    with pytest.raises(PermissionError):
        g.authorize(p, "dev-2", is_admin=False)
    g.authorize(p, "dev-2", is_admin=True)  # admin overrides


def test_release_requires_owner_or_admin():
    g = Game()
    p = g.add_player("Ana", "F", "Red")
    g.claim_seat(p, "dev-1")
    with pytest.raises(PermissionError):
        g.release_seat(p, "dev-2", is_admin=False)
    g.release_seat(p, "dev-2", is_admin=True)
    assert p.claim_token is None


def test_claiming_second_seat_releases_first():
    """FIX 4: claiming a new seat releases any other seat owned by same device"""
    g = Game()
    p0 = g.add_player("Ana", "F", "Red")
    p1 = g.add_player("Bo", "F", "Blue")

    # Device claims seat 0
    g.claim_seat(p0, "dev-1")
    assert p0.claim_token == "dev-1"
    assert p1.claim_token is None

    # Same device claims seat 1 - should release seat 0
    g.claim_seat(p1, "dev-1")
    assert p0.claim_token is None
    assert p1.claim_token == "dev-1"
