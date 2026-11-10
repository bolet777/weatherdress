"""Fige les chiffres tabulaires d'Inter SemiBold.

Pygame 2.5 (SDL_ttf) ne permet pas d'activer la fonction OpenType ``tnum``.
Ce script recopie le fichier officiel et fait pointer les chiffres, les deux-points
et la ponctuation liée vers leurs variantes tabulaires. Le fichier d'origine
n'est pas modifié. Inter 4.1 ne déclare pas de nom réservé.

Usage : python3 scripts/bake_inter_tabular.py
"""

from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "fonts" / "inter" / "Inter-SemiBold.ttf"
DST = ROOT / "fonts" / "inter" / "Inter-SemiBold-Tabular.ttf"

_NAMES = {
    1: "Inter SemiBold Tabular",
    4: "Inter SemiBold Tabular",
    6: "Inter-SemiBold-Tabular",
    16: "Inter",
    17: "SemiBold Tabular",
}


def _tnum_map(font):
    gsub = font["GSUB"].table
    indexes = []
    for record in gsub.FeatureList.FeatureRecord:
        if record.FeatureTag == "tnum":
            indexes.extend(record.Feature.LookupListIndex)
    mapping = {}
    for index in indexes:
        lookup = gsub.LookupList.Lookup[index]
        if lookup.LookupType != 1:
            raise SystemExit(f"lookup tnum inattendu : type {lookup.LookupType}")
        for subtable in lookup.SubTable:
            mapping.update(subtable.mapping)
    if "zero" not in mapping or "colon" not in mapping:
        raise SystemExit("la fonction tnum ne couvre pas les chiffres ou les deux-points")
    return mapping


def _apply_cmap(font, mapping):
    changed = 0
    for table in font["cmap"].tables:
        if not table.isUnicode():
            continue
        for code, glyph in list(table.cmap.items()):
            replacement = mapping.get(glyph)
            if replacement and replacement != glyph:
                table.cmap[code] = replacement
                changed += 1
    if changed == 0:
        raise SystemExit("aucun caractère unicode n'a été redirigé")


def _rename(font):
    table = font["name"]
    for record in table.names:
        if record.nameID == 3:
            text = record.toUnicode()
            if "Tabular" not in text:
                table.setName(
                    text + " Tabular",
                    3,
                    record.platformID,
                    record.platEncID,
                    record.langID,
                )
    for name_id, text in _NAMES.items():
        table.setName(text, name_id, 3, 1, 0x409)
        table.setName(text, name_id, 1, 0, 0)


def main():
    font = TTFont(SRC)
    _apply_cmap(font, _tnum_map(font))
    _rename(font)
    font.save(DST)
    print(DST)


if __name__ == "__main__":
    main()
