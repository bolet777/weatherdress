import os
import tempfile

import character_assets


def test_resolve_falls_back_to_lower_number():
    with tempfile.TemporaryDirectory() as d:
        path1 = os.path.join(d, "hot_man1.png")
        open(path1, "wb").close()
        resolved = character_assets.resolve_character_png(d, "hot_man6")
        assert resolved == path1


def test_resolve_exact_match():
    with tempfile.TemporaryDirectory() as d:
        path3 = os.path.join(d, "normal_woman3.png")
        open(path3, "wb").close()
        assert character_assets.resolve_character_png(d, "normal_woman3") == path3


def test_resolve_none_when_missing():
    with tempfile.TemporaryDirectory() as d:
        assert character_assets.resolve_character_png(d, "cold_man2") is None


def test_resolve_nonstandard_name_file_exists():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "legacy.png")
        open(p, "wb").close()
        assert character_assets.resolve_character_png(d, "legacy") == p
