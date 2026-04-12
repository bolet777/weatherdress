import random


# Seuils de température pour le personnage de base
def character_type(temp, snow):
    if snow > 0:
        return "snow"
    if temp >= 28:
        return "veryhot"
    if temp >= 25:
        return "hot"
    if temp >= 17:
        return "normal"
    if temp >= -9:
        return "cold"
    return "verycold"


def pick_identity():
    """
    Choisi genre et numéro une seule fois au démarrage.
    Retourne ("woman", 1) ou ("man", 1) — extensible si on ajoute woman2, man2, etc.
    """
    gender = random.choice(["woman", "man"])
    return gender, 1


def active_accessories(weather):
    """
    Retourne la liste des accessoires actifs pour une tranche météo donnée.
    `weather` est un dict avec temp, rain, snow, wind_kmh, clouds, hour.
    """
    accessories = []

    if weather["rain"] > 0:
        accessories.append("umbrella")

    if weather["clouds"] < 30 and 7 <= weather["hour"] <= 17:
        accessories.append("sunglasses")

    # Chapeau : grand soleil ou très chaud
    if (weather["clouds"] < 20 and 9 <= weather["hour"] <= 16) or weather["temp"] >= 28:
        accessories.append("hat")

    if weather["snow"] > 0 or weather["rain"] > 5:
        accessories.append("boots")

    if weather["temp"] < 5 or weather["wind_kmh"] > 30:
        accessories.append("scarf")

    return accessories


def get_outfit(current_weather, forecast_slices):
    """
    Retourne un dict décrivant la tenue complète :
    - character: nom du fichier de base (ex: "cold_woman1")
    - current_accessories: liste de noms d'accessoires pour maintenant
    - future_accessories: liste de dicts {accessory, hour} pour les prochaines tranches
    """
    # L'identité est passée depuis main.py pour rester stable
    raise NotImplementedError("Utiliser get_outfit_with_identity()")


def get_outfit_with_identity(current_weather, forecast_slices, gender, number):
    ctype = character_type(current_weather["temp"], current_weather["snow"])
    character = f"{ctype}_{gender}{number}"

    current_acc = active_accessories(current_weather)

    # Pour chaque tranche future, calcule les accessoires et garde les nouveaux
    future_acc = []
    seen = set(current_acc)
    for slice_ in forecast_slices:
        for acc in active_accessories(slice_):
            if acc not in seen:
                future_acc.append({"accessory": acc, "hour": slice_["hour"]})
                seen.add(acc)

    return {
        "character": character,
        "current_accessories": current_acc,
        "future_accessories": future_acc,
    }
