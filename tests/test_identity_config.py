import weatherdress.identity_config as identity_config


def test_identity_explicit_true():
    assert identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": True, "refresh_minutes": 60}
    )


def test_identity_explicit_false_hourly_pi():
    assert not identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 60}
    )


def test_identity_explicit_false_one_minute_stable_character():
    assert not identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 1}
    )


def test_identity_explicit_false_five_minute_rotates():
    assert identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 5}
    )


def test_identity_heuristic_when_refresh_at_most_five_minutes():
    assert identity_config.identity_on_each_refresh({"refresh_minutes": 5})
    assert identity_config.identity_on_each_refresh({"refresh_minutes": 1})
    assert identity_config.identity_on_each_refresh({"refresh_minutes": 0})


def test_identity_no_key_long_refresh():
    assert not identity_config.identity_on_each_refresh({"refresh_minutes": 60})
