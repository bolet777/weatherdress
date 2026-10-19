import weatherdress.identity_config as identity_config


def test_identity_explicit_true_rotates_whatever_the_interval():
    assert identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": True, "refresh_minutes": 60}
    )
    assert identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": True, "refresh_minutes": 5}
    )
    assert identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": True, "refresh_minutes": 1}
    )


def test_identity_explicit_false_keeps_startup_character():
    assert not identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 60}
    )
    assert not identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 5}
    )
    assert not identity_config.identity_on_each_refresh(
        {"identity_on_each_refresh": False, "refresh_minutes": 1}
    )


def test_identity_absent_key_keeps_startup_character():
    assert not identity_config.identity_on_each_refresh({})
    assert not identity_config.identity_on_each_refresh({"refresh_minutes": 5})
    assert not identity_config.identity_on_each_refresh({"refresh_minutes": 60})
