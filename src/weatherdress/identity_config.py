def identity_on_each_refresh(config):
    """
    Nouveau couple genre / variante à chaque lecture météo.

    ``true`` : nouveau personnage à chaque lecture.
    ``false`` ou clé absente : personnage tiré une fois au démarrage et gardé.
    """
    return config.get("identity_on_each_refresh") is True
