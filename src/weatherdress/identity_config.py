def identity_on_each_refresh(config):
    """Nouveau personnage à chaque lecture météo, quel que soit l'intervalle.

    Activé : un nouveau personnage est tiré à chaque lecture.
    Désactivé ou clé absente : le personnage tiré au démarrage reste affiché.
    """
    return config.get("identity_on_each_refresh") is True
