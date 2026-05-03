import os
import re
from typing import List

# Nom de fichier : {condition}_{woman|man}{n}.png
CHARACTER_FILENAME_RE = re.compile(r"^(.+)_(woman|man)(\d+)$")


def list_character_variant_numbers(characters_dir: str, prefix: str, gender: str) -> List[int]:
    """Numéros ``n`` pour lesquels ``{prefix}_{gender}{n}.png`` existe."""
    if not characters_dir or not os.path.isdir(characters_dir):
        return []
    tail = re.compile(
        rf"^{re.escape(prefix)}_{re.escape(gender)}(\d+)\.png$",
        re.IGNORECASE,
    )
    nums: List[int] = []
    for name in os.listdir(characters_dir):
        m = tail.match(name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def resolve_character_png(characters_dir, character_base):
    """
    Chemin du premier PNG trouvé en essayant le numéro demandé, puis n-1 … 1.
    Sinon None. `character_base` sans extension (ex. "hot_woman4").
    """
    m = CHARACTER_FILENAME_RE.match(character_base)
    if not m:
        path = os.path.join(characters_dir, f"{character_base}.png")
        return path if os.path.isfile(path) else None

    prefix, gender, num = m.group(1), m.group(2), int(m.group(3))
    for n in range(num, 0, -1):
        path = os.path.join(characters_dir, f"{prefix}_{gender}{n}.png")
        if os.path.isfile(path):
            return path
    return None
