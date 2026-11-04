"""Dessin de l'agenda, repris tel quel de la maquette validée.

Le rectangle vient de l'appelant : cartes bus/métro, ou l'espace sous la météo
quand les transports sont absents. Aucun accès réseau ici.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

import pygame

HORIZON_DAYS = 4
ELLIPSIS = "…"
PANEL_PAD = 12
TIME_GAP = 10

TODAY_TIME = (168, 82, 22)
TODAY_TEXT = (28, 42, 84)
TODAY_HEADER = (18, 52, 125)
NEXT_TEXT = (70, 80, 102)
NEXT_TIME = (56, 66, 92)
WASH = (214, 228, 246)
DIVIDER = (196, 204, 216)

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

# Du plus lisible au plus compact. Le premier qui offre assez de lignes est gardé.
_STYLES = (
    {"header": 36, "today": 36, "next": 26, "gap_today": 4, "gap_next": 2, "min_slots": 4},
    {"header": 32, "today": 34, "next": 24, "gap_today": 3, "gap_next": 2, "min_slots": 4},
    {"header": 32, "today": 32, "next": 22, "gap_today": 3, "gap_next": 2, "min_slots": 3},
    {"header": 26, "today": 26, "next": 18, "gap_today": 2, "gap_next": 2, "min_slots": 2},
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
    def __init__(self, show, panel, pieces, divider_y=None, strip_w=0):
        self.show = show
        self.panel = panel
        self.pieces = pieces
        self.divider_y = divider_y
        self.strip_w = strip_w


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


def _font(px, bold):
    return pygame.font.SysFont("sans-serif", int(px), bold=bold)


def _slots_for(style, panel_h, today_font, next_font, header_font):
    pad = PANEL_PAD
    inner = panel_h - 2 * pad
    rhythm = max(4, style["gap_today"])
    next_row = next_font.get_height() + rhythm
    next_h = 3 * next_row - rhythm
    header_h = header_font.get_height()
    remain = inner - next_h - header_h - 3 * rhythm
    row = today_font.get_height() + style["gap_today"]
    if remain < today_font.get_height() or row <= 0:
        return 0, next_h, header_h
    slots = 1 + (remain - today_font.get_height()) // row
    return int(slots), next_h, header_h


def _pick_style(panel_h):
    """Polices : heures du jour en gras, titres d'événements en graisse normale."""
    chosen = None
    fonts = None
    slots = 0
    for style in _STYLES:
        header_font = _font(style["header"], True)
        today_time = _font(style["today"], True)
        today_title = _font(style["today"], False)
        next_font = _font(style["next"], False)
        row_font = today_time if today_time.get_height() >= today_title.get_height() else today_title
        slots, _next_h, _header_h = _slots_for(
            style, panel_h, row_font, next_font, header_font
        )
        chosen = style
        fonts = (header_font, today_time, today_title, next_font)
        if slots >= style["min_slots"]:
            break
    return chosen, fonts, slots


def _strip_width(panel_w):
    """Même largeur que le bandeau des cartes bus et métro."""
    from . import display

    return min(display.TRANSIT_STRIP_WIDTH, max(1, int(panel_w) // 3))


def _piece(text, role, zone, x, y, font, color, day_offset=None):
    width, height = font.size(text)
    rect = pygame.Rect(x, y, width, height)
    return Piece(text, role, zone, rect, color, day_offset)


def layout_agenda(events, now, panel):
    """Découpe le rectangle des cartes. Les heures ne sont jamais tronquées."""
    panel = pygame.Rect(panel)
    if not should_show_agenda(events, now) or panel.width < 80 or panel.height < 48:
        return AgendaLayout(False, panel, [])

    style, (header_font, today_time, today_title, next_font), slots = _pick_style(panel.height)
    today = now.date()
    strip_w = _strip_width(panel.w)
    content_left = panel.x + strip_w + PANEL_PAD
    content_right = panel.right - PANEL_PAD
    content_w = max(0, content_right - content_left)
    pieces = []
    rhythm = max(4, style["gap_today"])

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

    next_row_h = next_font.get_height() + rhythm
    next_h = 3 * next_row_h - rhythm

    today_events = events_on_day(events, today, now)
    today_top = header_y + header_font.get_height() + rhythm
    row_h = max(today_time.get_height(), today_title.get_height()) + style["gap_today"]
    if not today_events:
        pieces.append(
            _piece("—", "dash", "today", content_left, today_top, today_title, TODAY_TEXT, 0)
        )
    else:
        shown = today_events[: max(1, slots)]
        hidden = len(today_events) - len(shown)
        labels = [_time_label(event) for event in shown]
        time_col = max(today_time.size(label)[0] for label in labels)
        for index, event in enumerate(shown):
            y = today_top + index * row_h
            last = index == len(shown) - 1
            more = f"+{hidden}" if last and hidden else ""
            more_w = today_title.size(more)[0] if more else 0
            pieces.append(
                _piece(labels[index], "time", "today", content_left, y, today_time, TODAY_TIME, 0)
            )
            title_x = content_left + time_col + TIME_GAP
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
                        TODAY_HEADER,
                        0,
                    )
                )

    today_bottom = max(
        piece.rect.bottom for piece in pieces if piece.zone in ("header", "today")
    )
    # Le bleu s'arrête sous aujourd'hui. Les trois jours suivent tout de suite.
    divider_y = today_bottom + rhythm
    next_top = divider_y + rhythm
    max_next_top = panel.bottom - PANEL_PAD - next_h
    if next_top > max_next_top:
        next_top = max_next_top
        divider_y = min(divider_y, next_top - rhythm)

    day_labels = [format_day(today + timedelta(days=offset)) for offset in (1, 2, 3)]
    day_col = max(next_font.size(label)[0] for label in day_labels)
    sample_times = ["00:00", "Journée"]
    for offset in (1, 2, 3):
        day = today + timedelta(days=offset)
        found = events_on_day(events, day, now)
        if found:
            sample_times.append(_time_label(found[0]))
    time_col = max(next_font.size(label)[0] for label in sample_times)

    for index, offset in enumerate((1, 2, 3)):
        day = today + timedelta(days=offset)
        y = next_top + index * next_row_h
        pieces.append(
            _piece(
                day_labels[index],
                "day",
                "upcoming",
                content_left,
                y,
                next_font,
                NEXT_TEXT,
                offset,
            )
        )
        found = events_on_day(events, day, now)
        time_x = content_left + day_col + TIME_GAP
        if not found:
            pieces.append(
                _piece("—", "dash", "upcoming", time_x, y, next_font, NEXT_TEXT, offset)
            )
            continue
        label = _time_label(found[0])
        pieces.append(
            _piece(label, "time", "upcoming", time_x, y, next_font, NEXT_TIME, offset)
        )
        extra = len(found) - 1
        more = f"+{extra}" if extra else ""
        more_w = next_font.size(more)[0] if more else 0
        title_x = time_x + time_col + TIME_GAP
        reserve = (TIME_GAP + more_w) if more else 0
        title = fit_ellipsis(next_font, found[0].title, content_right - title_x - reserve)
        if title:
            pieces.append(
                _piece(title, "title", "upcoming", title_x, y, next_font, NEXT_TEXT, offset)
            )
        if more:
            more_x = content_right - more_w
            pieces.append(
                _piece(more, "more", "upcoming", more_x, y, next_font, NEXT_TIME, offset)
            )

    return AgendaLayout(True, panel, pieces, divider_y, strip_w)


def paint_agenda(screen, laid):
    from . import display

    panel = laid.panel
    if panel.height <= 0 or not laid.show:
        return
    radius = display.TRANSIT_CARD_BORDER_RADIUS
    strip_w = laid.strip_w or _strip_width(panel.w)
    display._transit_blit_card_shadow(screen, panel, radius)
    clip = screen.get_clip()
    screen.set_clip(panel)
    pygame.draw.rect(screen, display.TRANSIT_CARD_BG, panel, border_radius=radius)
    rail = pygame.Rect(panel.x, panel.y, strip_w, panel.h)
    pygame.draw.rect(
        screen,
        display.TRANSIT_CARD_STRIP_BUS,
        rail,
        border_top_left_radius=radius,
        border_bottom_left_radius=radius,
    )
    if laid.divider_y is not None:
        wash = pygame.Rect(
            panel.x + strip_w,
            panel.y,
            max(0, panel.w - strip_w),
            max(0, laid.divider_y - panel.y),
        )
        if wash.height > 0 and wash.width > 0:
            pygame.draw.rect(
                screen,
                WASH,
                wash,
                border_top_right_radius=radius,
            )
        pygame.draw.line(
            screen,
            DIVIDER,
            (panel.x + strip_w + 8, laid.divider_y),
            (panel.right - 10, laid.divider_y),
            1,
        )
    _blit_calendar_icon(screen, rail)
    screen.set_clip(clip)
    _paint_pieces(screen, laid)


def _blit_calendar_icon(screen, strip):
    """Icône calendrier blanche, centrée dans le bandeau."""
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
        center = (body.left + int(body.w * frac), body.top)
        pygame.draw.circle(big, white, center, ring_r, width=width)
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
    screen.blit(icon, icon.get_rect(center=strip.center))


def _paint_pieces(screen, laid):
    """Blitte chaque morceau avec la police qui a servi à mesurer le rectangle."""
    _style, fonts, _slots = _pick_style(laid.panel.height)
    header_font, today_time, today_title, next_font = fonts
    clip = screen.get_clip()
    screen.set_clip(laid.panel)
    for piece in laid.pieces:
        if piece.zone == "header":
            font = header_font
        elif piece.zone == "today" and piece.role == "time":
            font = today_time
        elif piece.zone == "today":
            font = today_title
        else:
            font = next_font
        surf = font.render(piece.text, True, piece.color)
        screen.blit(surf, piece.rect.topleft)
    screen.set_clip(clip)
