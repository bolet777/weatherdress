import pygame

from weatherdress.future_accessories_column import (
    COLUMN_MAX_TOTAL,
    draw_future_accessories_column,
    urgency_pct,
    _build_slots,
)


def test_urgency_pct_zero_hours_is_max():
    assert urgency_pct(0, 8) == 100


def test_urgency_pct_at_or_beyond_horizon_clamps_minimum():
    assert urgency_pct(8, 8) == 5
    assert urgency_pct(12, 8) == 5


def test_urgency_pct_mid_range():
    # h=4, fh=8 -> 50%
    assert urgency_pct(4, 8) == 50


def test_urgency_pct_never_below_five_when_far():
    assert urgency_pct(100, 8) == 5


def test_urgency_pct_invalid_forecast_defaults():
    assert urgency_pct(2, None) == urgency_pct(2, 8)


def test_build_slots_future_sorted_by_hours_from_now():
    cur: list = []
    fut = [
        {"accessory": "far", "hours_from_now": 9, "hour": 20},
        {"accessory": "soon", "hours_from_now": 2, "hour": 14},
        {"accessory": "mid", "hours_from_now": 5, "hour": 17},
    ]
    slots = _build_slots(cur, fut, 10)
    assert [s[1] for s in slots] == ["soon", "mid", "far"]


def test_build_slots_current_first_then_future_capped():
    cur = ["a", "b"]
    fut = [{"accessory": "u"}, {"accessory": "v"}, {"accessory": "w"}]
    slots = _build_slots(cur, fut, COLUMN_MAX_TOTAL)
    kinds = [s[0] for s in slots]
    ids = [s[1] for s in slots]
    assert len(slots) == COLUMN_MAX_TOTAL
    assert kinds == ["current", "current", "future", "future"]
    assert ids == ["a", "b", "u", "v"]


def test_draw_column_many_items_short_character_no_crash(tmp_path):
    """Colonne serrée verticalement : réduction ou retrait d’items sans débordement."""
    pygame.init()
    screen = pygame.Surface((800, 480))
    char_rect = pygame.Rect(220, 90, 120, 140)
    fut = [
        {"accessory": "a", "hour": 12, "hours_from_now": 1},
        {"accessory": "b", "hour": 15, "hours_from_now": 3},
        {"accessory": "c", "hour": 18, "hours_from_now": 5},
        {"accessory": "d", "hour": 21, "hours_from_now": 7},
    ]
    draw_future_accessories_column(
        screen,
        ["cap", "scarf"],
        fut,
        char_rect,
        str(tmp_path),
        {"forecast_hours": 8},
    )
