"""Dessin de l'agenda dans le même chrome que les cartes de transport.

Le rectangle vient de l'appelant : cartes bus/métro, ou l'espace sous la météo
quand les transports sont absents. Aucun accès réseau ici.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

import pygame

from . import fonts

HORIZON_DAYS = 4
ELLIPSIS = "…"
PANEL_PAD = 12
TIME_GAP = 10
MIN_GAP = 6
MAX_TODAY_SLOTS = 5
_MIN_PX = 16
_MAX_PX = 24
# On ajoute une ligne si la police reste assez grande pour être lue de loin.
_FONT_FLOOR = 0.80

TODAY_TIME = (242, 164, 62)
TODAY_TEXT = (255, 255, 255)
TODAY_HEADER = (255, 255, 255)
NEXT_TEXT = (255, 255, 255)
NEXT_TIME = (242, 164, 62)
WASH_RGBA = (255, 255, 255, 64)
EVENT_WASH_RGBA = (255, 206, 130, 96)
# Filets de l'agenda, visibles sur le verre clair.
AGENDA_RULE = (32, 44, 62, 80)

_WEEKDAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
_MONTHS = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)



class Event:
    def __init__(self, start, end, title, all_day=False):
        self.start = start
        self.end = end
        self.title = title
        self.all_day = bool(all_day)


class Piece:
    def __init__(self, text, role, zone, rect, color, day_offset=None):
        self.text = text
        self.role = role
        self.zone = zone
        self.rect = rect
        self.color = color
        self.day_offset = day_offset


class AgendaLayout:
    def __init__(self, show, panel, pieces, divider_y=None, strip_w=0, fonts=None, bands=None, rule_x=None):
        self.show = show
        self.panel = panel
        self.pieces = pieces
        self.divider_y = divider_y
        self.strip_w = strip_w
        self.fonts = fonts
        self.bands = bands or []
        self.rule_x = rule_x


def display_enabled(config, events) -> bool:
    """Vrai seulement si l'agenda est activé et qu'un instantané a été fourni."""
    if events is None:
        return False
    block = config.get("calendar") if isinstance(config, dict) else None
    return isinstance(block, dict) and block.get("enabled") is True


def rotate_period(config) -> float:
    """Secondes entre deux coupes. 0 laisse un seul panneau. Valeur illisible : 15."""
    block = config.get("calendar") if isinstance(config, dict) else None
    raw = 15 if not isinstance(block, dict) else block.get("rotate_seconds", 15)
    try:
        period = float(raw)
    except (TypeError, ValueError):
        return 15.0
    if period < 0:
        return 0.0
    return period


def choose_side(
    *,
    calendar_enabled,
    transit_enabled,
    has_events,
    rotate_seconds,
    phase_t,
) -> str:
    """'transit', 'calendar' ou 'none'. Coupe franche, sans état intermédiaire."""
    if not calendar_enabled or not has_events:
        return "transit" if transit_enabled else "none"
    if not transit_enabled:
        return "calendar"
    try:
        period = float(rotate_seconds)
    except (TypeError, ValueError):
        period = 15.0
    if period <= 0:
        return "transit"
    try:
        phase = int(float(phase_t) // period)
    except (TypeError, ValueError, OverflowError):
        phase = 0
    return "calendar" if phase % 2 else "transit"


def fit_ellipsis(font, text, max_width):
    """Coupe `text` avec une ellipse. Chaîne vide si même l'ellipse ne tient pas."""
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    ell_w = font.size(ELLIPSIS)[0]
    if ell_w > max_width:
        return ""
    lo, hi = 0, len(text)
    best = ELLIPSIS
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid].rstrip() + ELLIPSIS
        if font.size(candidate)[0] <= max_width:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def format_day(day):
    return f"{_WEEKDAYS[day.weekday()]} {day.day}"


def format_header_date(day):
    return f"{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month - 1]}"


def _wall(moment, tzinfo):
    """Ramène `moment` au même fuseau que l'événement, naïf ou conscient."""
    if tzinfo is None:
        if moment.tzinfo is None:
            return moment
        return moment.replace(tzinfo=None)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=tzinfo)
    return moment.astimezone(tzinfo)


def _covers_day(event, day):
    tz = event.start.tzinfo
    start_day = datetime.combine(day, dtime.min)
    if tz is not None:
        start_day = start_day.replace(tzinfo=tz)
    end_day = start_day + timedelta(days=1)
    end = event.end
    if end.tzinfo is None and tz is not None:
        end = end.replace(tzinfo=tz)
    elif end.tzinfo is not None and tz is None:
        end = end.replace(tzinfo=None)
    if event.all_day:
        return event.start.date() <= day < event.end.date()
    return event.start < end_day and end > start_day


def _relevant(event, day, now):
    if not _covers_day(event, day):
        return False
    if day == now.date() and not event.all_day and _wall(event.end, event.end.tzinfo) <= _wall(now, event.end.tzinfo):
        return False
    return True


def _sort_key(event):
    return (0 if event.all_day else 1, event.start, event.title)


def events_on_day(events, day, now):
    found = [event for event in events if _relevant(event, day, now)]
    found.sort(key=_sort_key)
    return found


def should_show_agenda(events, now):
    today = now.date()
    for offset in range(HORIZON_DAYS):
        if events_on_day(events, today + timedelta(days=offset), now):
            return True
    return False


def _time_label(event):
    if event.all_day:
        return "Journée"
    return event.start.strftime("%H:%M")


def _all_day_label_fits(time_font, title_font, title, room, more=""):
    """Vrai si « Journée » et le titre entier tiennent dans `room`."""
    if not title:
        return True
    more_w = (TIME_GAP + title_font.size(more)[0]) if more else 0
    need = time_font.size("Journée")[0] + TIME_GAP + title_font.size(title)[0] + more_w
    return need <= room


def _font(px, role):
    return fonts.load(px, role)


def _make_fonts(px):
    """Aujourd'hui et les trois jours partagent la même taille. Les heures sont tabulaires."""
    px = int(px)
    return (
        _font(px, "semibold"),
        _font(px, "semibold-tabular"),
        _font(px, "regular"),
        _font(px, "regular"),
    )


def _row_height(fonts):
    return max(font.get_height() for font in fonts)


def _title_reserve(font, title):
    """Un titre court reste entier. Un titre long garde le budget d'un titre de 12 lettres."""
    if not title:
        return 0
    if len(title) <= 12:
        return font.size(title)[0]
    return font.size("Anniversaire")[0]


def _rows_fit(fonts, content_w, today_rows, upcoming_rows):
    if content_w is None:
        return True
    header, today_time, today_title, next_font = fonts
    header_w = header.size("Aujourd'hui")[0] + header.size("mer. 4")[0] + 16
    if header_w > content_w:
        return False
    if today_rows:
        time_w = max(today_time.size(label)[0] for label, _title, _more in today_rows)
        for label, title, more in today_rows:
            width = time_w + TIME_GAP + _title_reserve(today_title, title)
            if more:
                width += TIME_GAP + today_title.size(more)[0]
            if width > content_w:
                return False
    if not upcoming_rows:
        return True
    day_w = max(next_font.size(day)[0] for day, _time, _title, _more in upcoming_rows)
    time_w = max(today_time.size(label)[0] for _day, label, _title, _more in upcoming_rows)
    for _day, _label, title, more in upcoming_rows:
        width = day_w + TIME_GAP + time_w
        if title:
            width += TIME_GAP + _title_reserve(next_font, title)
        if more:
            width += TIME_GAP + next_font.size(more)[0]
        if width > content_w:
            return False
    return True


def _largest_fit(panel_h, slots, content_w, lo, hi, today_rows, upcoming_rows):
    inner = int(panel_h) - 2 * PANEL_PAD
    n_lines = 1 + int(slots) + 3
    n_gaps = n_lines - 1
    for px in range(int(hi), int(lo) - 1, -1):
        fonts = _make_fonts(px)
        if not _rows_fit(fonts, content_w, today_rows, upcoming_rows):
            continue
        row_h = _row_height(fonts)
        if n_lines * row_h + n_gaps * MIN_GAP <= inner:
            return px, fonts, row_h
    return None


def _today_rows_for(events, slots):
    shown = list(events[:slots])
    hidden = len(events) - len(shown)
    rows = []
    for index, event in enumerate(shown):
        more = f"+{hidden}" if hidden and index == len(shown) - 1 else ""
        rows.append((_time_label(event), event.title, more))
    return rows


def _pick_style(panel_h, today_events=(), content_w=None, upcoming_rows=()):
    """Le plus grand corps qui laisse les heures entières, puis autant de lignes que ce corps permet."""
    today_events = list(today_events or [])
    hi = _MAX_PX
    if not today_events:
        found = _largest_fit(panel_h, 0, content_w, _MIN_PX, hi, [], upcoming_rows)
        if found is None:
            fonts = _make_fonts(_MIN_PX)
            return {"px": _MIN_PX}, fonts, 0
        px, fonts, _row_h = found
        return {"px": px}, fonts, 0
    wanted = min(MAX_TODAY_SLOTS, len(today_events))
    one_rows = _today_rows_for(today_events, 1)
    one = _largest_fit(panel_h, 1, content_w, _MIN_PX, hi, one_rows, upcoming_rows)
    if one is None:
        fonts = _make_fonts(_MIN_PX)
        return {"px": _MIN_PX}, fonts, 1
    floor = max(_MIN_PX, int(one[0] * _FONT_FLOOR))
    for slots in range(wanted, 0, -1):
        found = _largest_fit(
            panel_h,
            slots,
            content_w,
            floor,
            hi,
            _today_rows_for(today_events, slots),
            upcoming_rows,
        )
        if found is not None:
            px, fonts, _row_h = found
            return {"px": px}, fonts, slots
    px, fonts, _row_h = one
    return {"px": px}, fonts, 1


def _strip_width(panel_w, panel_h):
    """Même gouttière que le badge des cartes bus et métro."""
    from . import display

    return display.transit_content_gutter(panel_w, panel_h)


def _piece(text, role, zone, x, y, font, color, day_offset=None):
    width, height = font.size(text)
    rect = pygame.Rect(x, y, width, height)
    return Piece(text, role, zone, rect, color, day_offset)


def layout_agenda(events, now, panel):
    """Découpe le rectangle des cartes. Les heures ne sont jamais tronquées."""
    panel = pygame.Rect(panel)
    if not should_show_agenda(events, now) or panel.width < 80 or panel.height < 48:
        return AgendaLayout(False, panel, [])

    today = now.date()
    strip_w = _strip_width(panel.w, panel.h)
    content_left = panel.x + strip_w + PANEL_PAD
    content_right = panel.right - PANEL_PAD
    content_w = max(0, content_right - content_left)
    today_events = events_on_day(events, today, now)
    upcoming_rows = []
    for offset in (1, 2, 3):
        day = today + timedelta(days=offset)
        found = events_on_day(events, day, now)
        label = _time_label(found[0]) if found else "—"
        title = found[0].title if found else ""
        more = f"+{len(found) - 1}" if found and len(found) > 1 else ""
        upcoming_rows.append((format_day(day), label, title, more))
    _style, fonts, slots = _pick_style(panel.height, today_events, content_w, upcoming_rows)
    header_font, today_time, today_title, next_font = fonts
    pieces = []
    n_lines = 1 + slots + 3
    n_gaps = n_lines - 1
    row_h = _row_height(fonts)
    inner = panel.h - 2 * PANEL_PAD
    gap = max(0, (inner - n_lines * row_h) // n_gaps)
    stride = row_h + gap

    header_text = "Aujourd'hui"
    date_text = format_header_date(today)
    if header_font.size(header_text)[0] + header_font.size(date_text)[0] + 16 > content_w:
        date_text = format_day(today)
    header_y = panel.y + PANEL_PAD
    pieces.append(
        _piece(header_text, "header", "header", content_left, header_y, header_font, TODAY_HEADER)
    )
    date_w = header_font.size(date_text)[0]
    pieces.append(
        _piece(
            date_text,
            "date",
            "header",
            content_right - date_w,
            header_y,
            header_font,
            TODAY_HEADER,
        )
    )

    today_top = header_y + stride
    if today_events:
        shown = today_events[: max(1, slots)]
        hidden = len(today_events) - len(shown)
        visible = []
        for index, event in enumerate(shown):
            last = index == len(shown) - 1
            more = f"+{hidden}" if last and hidden else ""
            label = _time_label(event)
            if event.all_day and not _all_day_label_fits(
                today_time, today_title, event.title, content_w, more
            ):
                label = ""
            visible.append((event, label, more))
        timed = [label for _event, label, _more in visible if label]
        time_col = max((today_time.size(label)[0] for label in timed), default=0)
        for index, (event, label, more) in enumerate(visible):
            y = today_top + index * stride
            more_w = today_title.size(more)[0] if more else 0
            if label:
                pieces.append(
                    _piece(label, "time", "today", content_left, y, today_time, TODAY_TIME, 0)
                )
                title_x = content_left + time_col + TIME_GAP
            else:
                title_x = content_left
            reserve = (TIME_GAP + more_w) if more else 0
            title = fit_ellipsis(today_title, event.title, content_right - title_x - reserve)
            if title:
                pieces.append(
                    _piece(title, "title", "today", title_x, y, today_title, TODAY_TEXT, 0)
                )
            if more:
                pieces.append(
                    _piece(
                        more,
                        "more",
                        "today",
                        content_right - more_w,
                        y,
                        today_title,
                        NEXT_TEXT,
                        0,
                    )
                )

    next_top = header_y + (1 + slots) * stride

    day_col = max(next_font.size(day)[0] for day, _label, _title, _more in upcoming_rows)
    time_room = content_w - day_col - TIME_GAP
    shown_upcoming = []
    for day_label, label, title, more in upcoming_rows:
        if label == "Journée" and not _all_day_label_fits(
            today_time, next_font, title, time_room, more
        ):
            label = ""
        shown_upcoming.append((day_label, label, title, more))
    time_col = max(
        (today_time.size(label)[0] for _day, label, _title, _more in shown_upcoming if label),
        default=0,
    )

    for index, (day_label, label, title_text, more) in enumerate(shown_upcoming):
        y = next_top + index * stride
        offset = index + 1
        pieces.append(
            _piece(
                day_label,
                "day",
                "upcoming",
                content_left,
                y,
                next_font,
                NEXT_TEXT,
                offset,
            )
        )
        time_x = content_left + day_col + TIME_GAP
        if label == "—":
            pieces.append(
                _piece("—", "dash", "upcoming", time_x, y, next_font, NEXT_TEXT, offset)
            )
            continue
        if label:
            pieces.append(
                _piece(label, "time", "upcoming", time_x, y, today_time, NEXT_TIME, offset)
            )
            title_x = time_x + time_col + TIME_GAP
        else:
            title_x = time_x
        more_w = next_font.size(more)[0] if more else 0
        reserve = (TIME_GAP + more_w) if more else 0
        title = fit_ellipsis(next_font, title_text, content_right - title_x - reserve)
        if title:
            pieces.append(
                _piece(title, "title", "upcoming", title_x, y, next_font, NEXT_TEXT, offset)
            )
        if more:
            more_x = content_right - more_w
            pieces.append(
                _piece(more, "more", "upcoming", more_x, y, next_font, NEXT_TEXT, offset)
            )

    today_bottom = max(
        piece.rect.bottom for piece in pieces if piece.zone in ("header", "today")
    )
    upcoming_top = min(piece.rect.top for piece in pieces if piece.zone == "upcoming")
    divider_y = today_bottom + max(1, (upcoming_top - today_bottom) // 2)
    bands = _day_bands(panel, strip_w, next_top, stride, row_h, divider_y, shown_upcoming)
    rule_x = content_left + day_col + max(4, TIME_GAP // 2)
    return AgendaLayout(True, panel, pieces, divider_y, strip_w, fonts, bands, rule_x)


def _day_bands(panel, strip_w, next_top, stride, row_h, divider_y, rows):
    """Trois bandes sous aujourd'hui. La bande d'un jour occupé est marquée."""
    gap = max(0, stride - row_h)
    tops = [next_top + index * stride for index in range(3)]
    edges = [divider_y]
    for index in range(2):
        edges.append(tops[index] + row_h + max(1, gap // 2))
    edges.append(min(panel.bottom - 2, tops[2] + row_h + max(1, gap // 2)))
    bands = []
    for index, (_day, label, title, _more) in enumerate(rows):
        rect = pygame.Rect(
            panel.x + strip_w,
            edges[index],
            max(0, panel.w - strip_w),
            max(0, edges[index + 1] - edges[index]),
        )
        hot = bool(title) or label not in ("", "—")
        bands.append((rect, hot))
    return bands


def today_wash_on(background):
    """Couleur d’un pixel du lavis « aujourd’hui » une fois composé sur `background`."""
    from . import display

    sample = pygame.Surface((48, 48))
    sample.fill(background)

    def extra(big, scale):
        display._glass_fill(
            big, scale, pygame.Rect(0, 0, 48, 48), WASH_RGBA
        )

    display.paint_glass_card(sample, pygame.Rect(0, 0, 48, 48), extra)
    pixel = sample.get_at((24, 24))
    return (pixel.r, pixel.g, pixel.b)


def paint_agenda(screen, laid):
    from . import display

    panel = laid.panel
    if panel.height <= 0 or not laid.show:
        return
    radius = display.TRANSIT_CARD_BORDER_RADIUS
    strip_w = laid.strip_w or _strip_width(panel.w, panel.h)
    badge = display.transit_badge_rect(panel)
    badge_local = badge.move(-panel.x, -panel.y)

    def extra(big, scale):
        if laid.divider_y is not None:
            wash = pygame.Rect(
                strip_w,
                0,
                max(0, panel.w - strip_w),
                max(0, laid.divider_y - panel.y),
            )
            if wash.width > 0 and wash.height > 0:
                display._glass_fill(
                    big,
                    scale,
                    wash,
                    WASH_RGBA,
                    border_top_right_radius=radius,
                )
            display._glass_line(
                big,
                scale,
                AGENDA_RULE,
                (strip_w + 8, laid.divider_y - panel.y),
                (panel.w - 10, laid.divider_y - panel.y),
            )
        for index, (band, hot) in enumerate(laid.bands):
            local = band.move(-panel.x, -panel.y)
            if hot and local.width > 0 and local.height > 0:
                corners = {}
                if band.bottom >= panel.bottom - 3:
                    corners["border_bottom_right_radius"] = radius
                display._glass_fill(big, scale, local, EVENT_WASH_RGBA, **corners)
            if index:
                y = band.top - panel.y
                display._glass_line(
                    big,
                    scale,
                    AGENDA_RULE,
                    (strip_w + 8, y),
                    (panel.w - 10, y),
                )
        if laid.rule_x is not None and laid.bands:
            x = laid.rule_x - panel.x
            top = laid.bands[0][0].top - panel.y + 6
            bottom = laid.bands[-1][0].bottom - panel.y - 6
            display._glass_line(
                big,
                scale,
                AGENDA_RULE,
                (x, top),
                (x, bottom),
            )
        display._draw_badge_divider(big, scale, badge_local)

    display.paint_glass_card(screen, panel, extra)
    display.blit_mode_badge(screen, badge, None)
    _blit_calendar_icon(screen, badge, badge.center)
    _paint_pieces(screen, laid)


def _blit_calendar_icon(screen, strip, center=None):
    """Icône calendrier blanche, centrée dans le badge."""
    side = max(18, min(36, strip.w - 16, strip.h - 12))
    if side < 12:
        return
    scale = 3
    big = pygame.Surface((side * scale, side * scale), pygame.SRCALPHA)
    s = scale
    white = (255, 255, 255, 255)
    width = 2 * s
    body = pygame.Rect(2 * s, int(side * 0.24) * s, (side - 4) * s, int(side * 0.70) * s)
    radius = 3 * s
    pygame.draw.rect(big, white, body, width=width, border_radius=radius)
    head_h = max(width * 2, body.h // 5)
    head = pygame.Rect(body.left, body.top, body.w, head_h)
    pygame.draw.rect(
        big,
        white,
        head,
        border_top_left_radius=radius,
        border_top_right_radius=radius,
    )
    ring_r = max(2 * s, side * s // 10)
    for frac in (0.30, 0.70):
        ring_at = (body.left + int(body.w * frac), body.top)
        pygame.draw.circle(big, white, ring_at, ring_r, width=width)
    dot_r = max(s, side * s // 14)
    cols = (0.34, 0.66)
    rows = (0.48, 0.72)
    for row in rows:
        for col in cols:
            pygame.draw.circle(
                big,
                white,
                (body.left + int(body.w * col), body.top + int(body.h * row)),
                dot_r,
            )
    icon = pygame.transform.smoothscale(big, (side, side))
    point = center or strip.center
    placed = icon.get_rect(center=(strip.centerx, point[1]))
    if placed.top < strip.top + 4:
        placed.top = strip.top + 4
    if placed.bottom > strip.bottom - 4:
        placed.bottom = strip.bottom - 4
    screen.blit(icon, placed)


def _paint_pieces(screen, laid):
    """Blitte chaque morceau avec la police qui a servi à mesurer le rectangle."""
    fonts = laid.fonts
    if not fonts:
        _style, fonts, _slots = _pick_style(laid.panel.height)
    header_font, today_time, today_title, next_font = fonts
    clip = screen.get_clip()
    screen.set_clip(laid.panel)
    for piece in laid.pieces:
        if piece.zone == "header":
            font = header_font
        elif piece.role == "time":
            font = today_time
        elif piece.zone == "today":
            font = today_title
        else:
            font = next_font
        surf = font.render(piece.text, True, piece.color)
        screen.blit(surf, piece.rect.topleft)
    screen.set_clip(clip)
