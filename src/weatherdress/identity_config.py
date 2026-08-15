def _refresh_minutes(config):
    try:
        return int(config.get("refresh_minutes", 60))
    except (TypeError, ValueError):
        return 60


def identity_on_each_refresh(config):
    """
    Nouveau couple genre / variante à chaque fetch météo si True.

    - ``identity_on_each_refresh: true`` : toujours.
    - ``false`` + refresh ≥ 60 min : identité fixe (comportement Pi).
    - ``false`` + refresh ≤ 1 min : identité fixe (tests météo rapides).
    - ``false`` + refresh entre 2 et 59 min : rotation à chaque fetch
      (intervalle court = changement de personnage attendu).
    - Clé absente : rotation si ``refresh_minutes`` ≤ 5, sinon fixe au démarrage.
    """
    refresh = _refresh_minutes(config)

    if config.get("identity_on_each_refresh") is True:
        return True

    if config.get("identity_on_each_refresh") is False:
        if refresh <= 1:
            return False
        if refresh >= 60:
            return False
        return True

    return refresh <= 5
