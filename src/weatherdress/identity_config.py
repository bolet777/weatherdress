def identity_on_each_refresh(config):
    """
    Nouveau couple genre / variante à chaque fetch météo si True.
    Clé explicite prioritaire ; sinon refresh ≤ 1 min active la rotation (tests).
    """
    if "identity_on_each_refresh" in config:
        return bool(config["identity_on_each_refresh"])
    try:
        return int(config.get("refresh_minutes", 60)) <= 1
    except (TypeError, ValueError):
        return False
