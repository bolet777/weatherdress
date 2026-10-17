"""
Colonne d'icônes pour accessoires actuels et futurs (anneaux + pastilles
heure pour le futur uniquement).
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import pygame

from .badges import BADGE_FONT_PX, BADGE_PADDING, draw_badge

COLUMN_MAX_TOTAL = 4

# Anticrénelage : cercle + arcs dessinés en haute résolution puis lissés à l’échelle écran.
COLUMN_DISK_SUPERSAMPLE = 4

# Rétractation du rayon extérieur de l’anneau (px hi-res) pour le garder entièrement
# sur le plateau opaque : sinon smoothscale mélange la couleur à (0,0,0,0) → frange noire.
COLUMN_RING_OUTER_INSET_HI_MIN = 2

# Taille disques (levier unique) : historique × +15 % × +20 %.
COLUMN_OUTER_RADIUS_SCALE = 1.625 * 1.15 * 1.2

# Épaisseur de l’anneau = ratio du rayon extérieur (comme max(4, outer//6) avant plafond fixe).
COLUMN_RING_WIDTH_OVER_OUTER_RADIUS = 1.0 / 6.0


# Pastille heure (futur) : centre sur le bord du plateau, direction haut-droite (45°).
_COLUMN_BADGE_DIR_XY = math.sqrt(0.5)  # cos(π/4), sin(π/4) — unitaire écran (+x, -y)


# Colonne : espace entre le bord droit du disque et char_rect.left ; marge écran à gauche.
COLUMN_TO_CHARACTER_GAP_PX = 10
COLUMN_SCREEN_LEFT_MARGIN_PX = 8
COLUMN_SCREEN_TOP_MARGIN_PX = 8
# Rayon extérieur minimal (icône encore lisible dans l’anneau).
COLUMN_OUTER_R_READABILITY_MIN = 22


def _disk_canvas_half_extent(outer_r: int, ring_w: int) -> Tuple[int, int]:
    """Largeur du carré du sprite disque (cw) et demi-côté pour centrer (cx0)."""
    arc_r = outer_r - ring_w // 2
    half_need = arc_r + ring_w + 2
    pw0 = outer_r * 2 + 4
    cw = max(pw0, 2 * half_need)
    return cw, cw // 2


# Anneau « maintenant » : complet, blanc / neutre (pas de pastille heure)
CURRENT_RING_RGB = (235, 237, 242)


def urgency_pct(hours_from_now: float, forecast_hours: float) -> int:
    """
    Urgence pour l'anneau : bientôt = % élevé, aligné sur la fenêtre de
    prévision. Plage [5, 100] pour garder l'arc toujours un peu visible.
    """
    try:
        fh = float(forecast_hours)
    except (TypeError, ValueError):
        fh = 8.0
    fh = max(1.0, fh)
    try:
        h = float(hours_from_now)
    except (TypeError, ValueError):
        h = 1.0
    h = max(0.0, h)
    raw = 100.0 * (1.0 - h / fh)
    return int(max(5, min(100, round(raw))))


def _ring_rgb(pct: int) -> Tuple[int, int, int]:
    """Bientôt (pct élevé) → vert ; lointain (pct bas) → rouge ; orange entre."""
    t = max(0.0, min(1.0, pct / 100.0))
    green = (40, 190, 95)
    orange = (245, 130, 35)
    red = (215, 55, 55)
    if t >= 0.5:
        u = (t - 0.5) * 2.0
        return tuple(
            int(green[i] + u * (orange[i] - green[i])) for i in range(3)
        )
    u = t * 2.0
    return tuple(int(red[i] + u * (orange[i] - red[i])) for i in range(3))


def _load_png(path: str):
    """Charge le PNG à la résolution fichier (ex. 256×256) ; pas de redimensionnement ici."""
    if not os.path.exists(path):
        return None
    return pygame.image.load(path).convert_alpha()


def _fit_inside(img, max_w: int, max_h: int):
    """
    Une seule passe ``smoothscale`` depuis la surface chargée : réduction pour
    tenir dans la boîte, sans upscale (évite le flou si on part d’une surface
    déjà petite).
    """
    w, h = img.get_size()
    if w <= 0 or h <= 0 or max_w <= 0 or max_h <= 0:
        return img
    scale = min(max_w / w, max_h / h)
    if scale >= 1.0:
        return img
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    if (nw, nh) == (w, h):
        return img
    return pygame.transform.smoothscale(img, (nw, nh))


def _apply_colorkey(surface, config: Dict[str, Any]):
    raw = config.get("character_colorkey")
    if raw is None:
        return surface
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        rgb = tuple(max(0, min(255, int(c))) for c in raw)
        out = surface.copy()
        out.set_colorkey(rgb)
        return out
    return surface


def _draw_rounded_disk_like_time_pill(
    surf: pygame.Surface,
    cx: int,
    cy: int,
    r: int,
    rgba: Tuple[int, int, int, int],
) -> None:
    """
    Disque plein lisse : comme le fond du widget horloge (`draw_time_pill`) —
    carré centré 2r×2r avec ``border_radius`` maximal (silhouette circulaire),
    sur la surface hi-res puis réduit par ``smoothscale`` par l’appelant.
    """
    if r < 1:
        return
    d = 2 * r
    rect = pygame.Rect(int(cx - r), int(cy - r), d, d)
    br = min(r, rect.w // 2, rect.h // 2)
    pygame.draw.rect(surf, rgba, rect, border_radius=br)


def _rgb_to_rgba(
    color: Tuple[int, ...],
) -> Tuple[int, int, int, int]:
    if len(color) == 4:
        return int(color[0]), int(color[1]), int(color[2]), int(color[3])
    return int(color[0]), int(color[1]), int(color[2]), 255


def _fill_annulus_full(
    surf: pygame.Surface,
    cx: float,
    cy: float,
    r_outer: float,
    r_inner: float,
    rgba: Tuple[int, int, int, int],
) -> None:
    """
    Anneau 360° comme polygone (bords extérieur + intérieur).
    On évite le trou en ``(0,0,0,0)`` : sur SDL il laisse souvent une frange
    noire après ``smoothscale``, visible comme « bordure » sur l’anneau.
    """
    ro = float(r_outer)
    ri = float(r_inner)
    if ro <= ri + 1e-6:
        return
    steps = max(32, int(round(ro * 2.0)))
    pts: List[Tuple[float, float]] = []
    for i in range(steps + 1):
        t = 2 * math.pi * (i / steps)
        pts.append((cx + ro * math.cos(t), cy + ro * math.sin(t)))
    for i in range(steps, -1, -1):
        t = 2 * math.pi * (i / steps)
        pts.append((cx + ri * math.cos(t), cy + ri * math.sin(t)))
    pi_pts = [(int(round(x)), int(round(y))) for x, y in pts]
    pygame.draw.polygon(surf, rgba, pi_pts)


def _fill_annulus_sector(
    surf: pygame.Surface,
    cx: float,
    cy: float,
    r_inner: float,
    r_outer: float,
    angle_start: float,
    angle_end: float,
    rgba: Tuple[int, int, int, int],
) -> None:
    """
    Secteur d’anneau (pas d’arc pygame) : polygone fermé bords extérieur / intérieur,
    même logique à l’échelle hi puis un seul smoothscale sur toute la surface.
    """
    span = angle_end - angle_start
    if span <= 1e-9:
        return
    if span >= 2 * math.pi - 1e-6:
        _fill_annulus_full(surf, cx, cy, r_outer, r_inner, rgba)
        return
    steps = max(10, int(round(abs(span) * r_outer / 5.0)))
    pts: List[Tuple[float, float]] = []
    for i in range(steps + 1):
        t = angle_start + span * (i / steps)
        pts.append(
            (cx + r_outer * math.cos(t), cy + r_outer * math.sin(t))
        )
    for i in range(steps, -1, -1):
        t = angle_start + span * (i / steps)
        pts.append(
            (cx + r_inner * math.cos(t), cy + r_inner * math.sin(t))
        )
    pi_pts = [(int(round(x)), int(round(y))) for x, y in pts]
    pygame.draw.polygon(surf, rgba, pi_pts)


def _render_supersampled_accessory_disk(
    outer_r: int,
    ring_w: int,
    pct: int,
    progress_rgb: Tuple[int, int, int],
    plate_rgba: Tuple[int, int, int, int],
    track_rgba: Tuple[int, int, int, int],
) -> Tuple[pygame.Surface, int]:
    """
    Disque plateau supersamplé : plateau puis anneau piste + progression sur la
    **même** surface hi-res, un seul ``smoothscale``. L’anneau est légèrement
    rétracté pour ne pas coïncider avec le bord silhouette du plateau (évite halo
    noir aux bords clairs).
    """
    cw, cx0 = _disk_canvas_half_extent(outer_r, ring_w)
    arc_r = outer_r - ring_w // 2

    ss = COLUMN_DISK_SUPERSAMPLE
    cw_hi = cw * ss
    cx_hi = cx0 * ss
    cy_hi = cx0 * ss
    r_plate_hi = int(round(outer_r * ss))
    arc_r_hi = arc_r * ss
    arc_w_hi = max(1, ring_w * ss)
    r_outer_hi = arc_r_hi + arc_w_hi / 2.0
    r_inner_hi = max(1.0, arc_r_hi - arc_w_hi / 2.0)

    annulus_w = r_outer_hi - r_inner_hi
    min_inset = float(max(COLUMN_RING_OUTER_INSET_HI_MIN, ss))
    max_inset = max(0.0, annulus_w - 1.25)
    inset_hi = min(min_inset, max_inset) if max_inset > 0 else 0.0
    r_outer_draw = r_outer_hi - inset_hi

    hi_plate = pygame.Surface((cw_hi, cw_hi), pygame.SRCALPHA)
    _draw_rounded_disk_like_time_pill(
        hi_plate, int(cx_hi), int(cy_hi), int(r_plate_hi), plate_rgba
    )

    track_c = _rgb_to_rgba(track_rgba)
    _fill_annulus_full(
        hi_plate, float(cx_hi), float(cy_hi), r_outer_draw, r_inner_hi, track_c
    )

    span = max(0.01, (pct / 100.0) * 2 * math.pi)
    start_a = -math.pi / 2
    end_a = start_a + span
    prog_c = _rgb_to_rgba(progress_rgb)
    _fill_annulus_sector(
        hi_plate,
        float(cx_hi),
        float(cy_hi),
        r_inner_hi,
        r_outer_draw,
        start_a,
        end_a,
        prog_c,
    )

    out = pygame.transform.smoothscale(hi_plate, (cw, cw))
    return out, cx0


def _build_slots(
    current_accessory_ids: List[str],
    future_items: List[Dict[str, Any]],
    max_total: int,
) -> List[Tuple[str, str, Optional[Dict[str, Any]]]]:
    """
    Retourne des triplets ``("current"|"future", accessory_id, future_dict|None)``.
    Ordre : courants d'abord, puis futurs par ``hours_from_now`` croissant ;
    plafonné à ``max_total``.
    """
    out: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
    for acc_id in current_accessory_ids:
        if not acc_id:
            continue
        out.append(("current", acc_id, None))
        if len(out) >= max_total:
            return out
    for item in sorted(future_items, key=lambda it: float(it.get("hours_from_now") or 0)):
        if len(out) >= max_total:
            break
        aid = item.get("accessory", "")
        if not aid:
            continue
        out.append(("future", aid, item))
    return out


def draw_future_accessories_column(
    surface: pygame.Surface,
    current_accessory_ids: List[str],
    future_items: List[Dict[str, Any]],
    char_rect: pygame.Rect,
    images_dir: str,
    config: Dict[str, Any],
):
    """
    Colonne à gauche du personnage : puces pour accessoires actuels (anneau
    blanc 100 %, sans heure) puis futurs (urgence + pastille). Le bas du dernier
    disque (et pastille le cas échéant) ne dépasse pas ``char_rect.bottom``.
    """
    slots = _build_slots(
        current_accessory_ids,
        future_items,
        COLUMN_MAX_TOTAL,
    )
    if not slots:
        return

    fh = config.get("forecast_hours", 8)
    gutter = 12
    margin_left = COLUMN_SCREEN_LEFT_MARGIN_PX
    gap_y = 18
    top_y = COLUMN_SCREEN_TOP_MARGIN_PX
    h_dispo = max(1, char_rect.bottom - top_y)
    badge_r = BADGE_FONT_PX // 2 + BADGE_PADDING + 2
    u = _COLUMN_BADGE_DIR_XY

    left_strip_inner = max(40, char_rect.left - margin_left - gutter)
    _base_outer_r = max(22, min(46, left_strip_inner // 2))
    width_outer_r = max(1, int(round(_base_outer_r * COLUMN_OUTER_RADIUS_SCALE)))

    def _ring_w_for(outer_r: int) -> int:
        rw = max(4, int(round(outer_r * COLUMN_RING_WIDTH_OVER_OUTER_RADIUS)))
        return min(rw, max(4, outer_r // 2))

    def _vertical_extents(outer_r: int, ring_w: int, kind: str) -> Tuple[int, int]:
        _, disk_half = _disk_canvas_half_extent(outer_r, ring_w)
        above = disk_half
        below = disk_half
        if kind == "future":
            above = max(disk_half, int(round(u * outer_r + badge_r)))
            below = max(disk_half, int(round(badge_r - u * outer_r)))
        return above, below

    def _column_fits(outer_r: int, n: int, active_slots) -> bool:
        if outer_r < 1 or n < 1:
            return False
        ring_w = _ring_w_for(outer_r)
        cell_h = outer_r * 2 + gap_y
        above_last, below_last = _vertical_extents(
            outer_r, ring_w, active_slots[n - 1][0]
        )
        last_cy = char_rect.bottom - below_last
        first_cy = last_cy - (n - 1) * cell_h
        above_first, _ = _vertical_extents(outer_r, ring_w, active_slots[0][0])
        first_top = first_cy - above_first
        if first_top < top_y:
            return False
        stack_h = (n - 1) * cell_h + above_first + below_last
        return stack_h <= h_dispo

    def _largest_fitting_outer_r(n: int, active_slots, cap: int) -> int:
        lo = COLUMN_OUTER_R_READABILITY_MIN
        hi = max(lo, cap)
        best = 0
        for candidate in range(hi, lo - 1, -1):
            if _column_fits(candidate, n, active_slots):
                best = candidate
                break
        return best

    outer_r = 0
    while slots:
        n = len(slots)
        fit_r = _largest_fitting_outer_r(n, slots, width_outer_r)
        if fit_r >= COLUMN_OUTER_R_READABILITY_MIN:
            outer_r = fit_r
            break
        slots = slots[:-1]

    if not slots or outer_r < 1:
        return

    ring_w = _ring_w_for(outer_r)
    inner_pad = 3
    icon_max = max(12, (outer_r - ring_w - inner_pad) * 2 - 4)
    n = len(slots)
    cell_h = outer_r * 2 + gap_y
    _, disk_half = _disk_canvas_half_extent(outer_r, ring_w)
    ideal_cx = char_rect.left - COLUMN_TO_CHARACTER_GAP_PX - disk_half
    col_cx = max(COLUMN_SCREEN_LEFT_MARGIN_PX + disk_half, ideal_cx)

    _, below_last = _vertical_extents(outer_r, ring_w, slots[n - 1][0])
    last_cy = char_rect.bottom - below_last

    acc_dir = os.path.join(images_dir, "accessories")
    plate_rgba = (50, 54, 62, 210)
    track_rgba = (120, 125, 135, 200)

    for i, (kind, acc_id, fut) in enumerate(slots):
        cy = last_cy - (n - 1 - i) * cell_h
        cx = col_cx
        center = (cx, cy)

        if kind == "current":
            prog_rgb = CURRENT_RING_RGB
            pct_draw = 100
        else:
            assert fut is not None
            hfn = fut.get("hours_from_now", 1)
            pct_draw = urgency_pct(hfn, fh)
            prog_rgb = _ring_rgb(pct_draw)

        disk_surf, disk_half = _render_supersampled_accessory_disk(
            outer_r,
            ring_w,
            pct_draw,
            prog_rgb,
            plate_rgba,
            track_rgba,
        )
        surface.blit(disk_surf, (cx - disk_half, cy - disk_half))

        path = os.path.join(acc_dir, f"{acc_id}.png")
        img = _load_png(path)
        if img:
            img = _fit_inside(img, icon_max, icon_max)
            img = _apply_colorkey(img, config)
            ir = img.get_rect(center=center)
            surface.blit(img, ir)

        if kind == "future" and fut is not None:
            hour = fut.get("hour", 0)
            try:
                hb = int(hour)
            except (TypeError, ValueError):
                hb = 0
            badge_center = (
                int(round(cx + outer_r * u)),
                int(round(cy - outer_r * u)),
            )
            draw_badge(surface, f"{hb}H", badge_center)
