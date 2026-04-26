"""Horaires STM (GTFS statique + GTFS-RT pour les bus)."""

from __future__ import annotations

import csv
import io
import time
import zipfile
from datetime import date, datetime

import requests

from .paths import GTFS_CACHE_PATH

GTFS_CACHE_HOURS = 168  # 1 semaine

# Colonnes calendar.txt : indépendantes de la locale (strftime %A serait « lundi » en fr_FR).
WEEKDAY_COLUMNS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def weekday_column_for_date(d: date) -> str:
    """Colonne calendar.txt correspondant au jour (0 = lundi)."""
    return WEEKDAY_COLUMNS[d.weekday()]


def _zip_member(z: zipfile.ZipFile, filename: str) -> str:
    names = z.namelist()
    if filename in names:
        return filename
    for n in names:
        if n.endswith("/" + filename) or n.endswith("\\" + filename):
            return n
    raise FileNotFoundError(filename)


def _parse_departure_seconds(departure_time: str) -> int:
    """Secondes depuis minuit (GTFS peut utiliser heures > 24 pour le lendemain)."""
    parts = departure_time.strip().split(":")
    if len(parts) != 3:
        raise ValueError(departure_time)
    h, m, s = (int(parts[0]), int(parts[1]), int(parts[2]))
    return h * 3600 + m * 60 + s


class TransitFetcher:
    def __init__(self, config: dict):
        self.config = config["transit"]
        self._metro_index: list[tuple[str, int]] = []
        self._metro_trips: dict[str, dict[str, str]] = {}
        self._gtfs_path = GTFS_CACHE_PATH

    def initialize(self) -> None:
        """Télécharge le GTFS si besoin et construit l’index métro."""
        self._ensure_gtfs()
        self._build_metro_index()

    def _ensure_gtfs(self) -> None:
        path = self._gtfs_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            if age_hours < GTFS_CACHE_HOURS:
                return
        url = self.config["gtfs_url"]
        print("[transit] Téléchargement GTFS STM...")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
        print("[transit] GTFS téléchargé.")

    def _read_zip_csv(self, filename: str) -> list[dict[str, str]]:
        with zipfile.ZipFile(self._gtfs_path) as z:
            member = _zip_member(z, filename)
            with z.open(member) as f:
                return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

    def _read_zip_csv_optional(self, filename: str) -> list[dict[str, str]]:
        with zipfile.ZipFile(self._gtfs_path) as z:
            try:
                member = _zip_member(z, filename)
            except FileNotFoundError:
                return []
            with z.open(member) as f:
                return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

    def _build_metro_index(self) -> None:
        station_name = self.config["metro_station"]
        metro_route_id = str(self.config["metro_route_id"])

        stops = self._read_zip_csv("stops.txt")
        needle = station_name.lower()
        station_stop_ids = {
            s["stop_id"] for s in stops if needle in (s.get("stop_name") or "").lower()
        }
        if not station_stop_ids:
            print(f"[transit] Aucun arrêt métro ne correspond à « {station_name} ».")

        trips = self._read_zip_csv("trips.txt")
        self._metro_trips = {
            t["trip_id"]: {
                "headsign": t.get("trip_headsign") or "",
                "service_id": t["service_id"],
            }
            for t in trips
            if str(t.get("route_id", "")) == metro_route_id
        }

        self._metro_index = []
        print("[transit] Construction index métro (peut prendre ~30s sur un Pi)...")
        with zipfile.ZipFile(self._gtfs_path) as z:
            member = _zip_member(z, "stop_times.txt")
            with z.open(member) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    if row["stop_id"] not in station_stop_ids:
                        continue
                    if row["trip_id"] not in self._metro_trips:
                        continue
                    try:
                        dep_secs = _parse_departure_seconds(row["departure_time"])
                    except (ValueError, KeyError):
                        continue
                    self._metro_index.append((row["trip_id"], dep_secs))
        print(f"[transit] Index métro prêt ({len(self._metro_index)} passages).")

    def _active_service_ids(self) -> set[str]:
        today = date.today()
        weekday_col = weekday_column_for_date(today)
        today_str = today.strftime("%Y%m%d")

        active: set[str] = set()
        for r in self._read_zip_csv("calendar.txt"):
            if (
                r.get(weekday_col) == "1"
                and r.get("start_date", "") <= today_str <= r.get("end_date", "")
            ):
                active.add(r["service_id"])

        for r in self._read_zip_csv_optional("calendar_dates.txt"):
            if r.get("date") != today_str:
                continue
            if r.get("exception_type") == "1":
                active.add(r["service_id"])
            elif r.get("exception_type") == "2":
                active.discard(r["service_id"])
        return active

    def get_metro_departures(self) -> dict[str, list[int]]:
        """{trip_headsign: [minutes, ...]} — jusqu’à 3 prochains départs par direction."""
        if not self._metro_index or not self._metro_trips:
            return {}
        try:
            active = self._active_service_ids()
            now = datetime.now()
            now_secs = now.hour * 3600 + now.minute * 60 + now.second

            by_headsign: dict[str, list[int]] = {}
            for trip_id, dep_secs in self._metro_index:
                trip = self._metro_trips.get(trip_id)
                if not trip or trip["service_id"] not in active:
                    continue
                if dep_secs <= now_secs:
                    continue
                hs = trip["headsign"]
                by_headsign.setdefault(hs, []).append(dep_secs)

            result: dict[str, list[int]] = {}
            for headsign, times in by_headsign.items():
                times.sort()
                result[headsign] = [(t - now_secs) // 60 for t in times[:3]]
            return result
        except Exception as e:
            print(f"[transit] Erreur métro : {e}")
            return {}

    def get_bus_departures(self) -> dict[str, dict]:
        """GTFS-RT trip updates : {stop_id: {route, label, minutes}}."""
        key = (self.config.get("stm_api_key") or "").strip()
        if not key or key.upper().startswith("VOTRE_"):
            return {}
        bus_stops = self.config.get("bus_stops") or {}
        if not bus_stops:
            return {}
        stop_ids = {str(k) for k in bus_stops.keys()}
        try:
            url = "https://api.stm.info/pub/od/gtfs-rt/ic/v2/tripUpdates"
            r = requests.get(url, headers={"apikey": key}, timeout=15)
            if not r.ok:
                hint = (r.text or "").strip()[:240]
                if r.status_code == 400 and "Invalid API Key" in (r.text or ""):
                    print(
                        "[transit] Erreur bus : clé API STM refusée (400). "
                        "Vérifier stm_api_key sur le portail Données ouvertes / développeurs STM "
                        "(produit GTFS-RT trip updates), sans guillemets ni espace en trop."
                    )
                else:
                    print(f"[transit] Erreur bus HTTP {r.status_code}: {hint or r.reason}")
                return {}

            try:
                from google.transit import gtfs_realtime_pb2
            except ModuleNotFoundError:
                print(
                    "[transit] Paquet gtfs-realtime-bindings absent. "
                    "Sur le Pi : pip3 install --break-system-packages gtfs-realtime-bindings "
                    "ou bash scripts/install.sh"
                )
                return {}

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(r.content)

            now = int(time.time())
            result: dict[str, dict] = {}

            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue
                route_id = str(entity.trip_update.trip.route_id)
                for stu in entity.trip_update.stop_time_update:
                    sid = (stu.stop_id or "").strip()
                    if not sid or sid not in stop_ids:
                        continue
                    t = int(stu.arrival.time or stu.departure.time or 0)
                    if t <= now:
                        continue
                    minutes = (t - now) // 60
                    if sid not in result:
                        result[sid] = {
                            "route": route_id,
                            "label": bus_stops.get(sid, sid),
                            "minutes": [],
                        }
                    result[sid]["minutes"].append(minutes)

            for sid in result:
                result[sid]["minutes"].sort()
                result[sid]["minutes"] = result[sid]["minutes"][:3]

            return result
        except Exception as e:
            print(f"[transit] Erreur bus : {e}")
            return {}


def transit_config_enabled(config: dict) -> bool:
    t = config.get("transit")
    if not isinstance(t, dict):
        return False
    return bool(t.get("gtfs_url")) and bool(t.get("metro_station")) and (
        t.get("metro_route_id") is not None and str(t.get("metro_route_id")).strip() != ""
    )
