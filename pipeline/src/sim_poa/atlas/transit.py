"""Oferta de ônibus por parada e por hora, a partir do GTFS da Prefeitura.

O GTFS só traz horários nos pontos de controle; nas demais paradas da viagem
o horário fica em branco. Aqui ele é interpolado pela ordem das paradas entre
os pontos com horário, o que basta para contar ônibus por hora em cada parada.
"""

from __future__ import annotations

import datetime as dt
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _read(feed: zipfile.ZipFile, name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    with feed.open(name) as handle:
        return pd.read_csv(
            io.TextIOWrapper(handle, "utf-8-sig"), dtype=str, usecols=usecols, keep_default_na=False
        )


def active_services(feed: zipfile.ZipFile, day: dt.date) -> set[str]:
    stamp = day.strftime("%Y%m%d")
    services: set[str] = set()
    if "calendar.txt" in feed.namelist():
        calendar = _read(feed, "calendar.txt")
        running = calendar[
            calendar[WEEKDAYS[day.weekday()]].eq("1")
            & calendar["start_date"].le(stamp)
            & calendar["end_date"].ge(stamp)
        ]
        services |= set(running["service_id"])
    if "calendar_dates.txt" in feed.namelist():
        exceptions = _read(feed, "calendar_dates.txt")
        today = exceptions[exceptions["date"].eq(stamp)]
        services |= set(today.loc[today["exception_type"].eq("1"), "service_id"])
        services -= set(today.loc[today["exception_type"].eq("2"), "service_id"])
    return services


def feed_window(feed: zipfile.ZipFile) -> tuple[dt.date, dt.date]:
    calendar = _read(feed, "calendar.txt", ["start_date", "end_date"])
    return _date(str(calendar["start_date"].min())), _date(str(calendar["end_date"].max()))


def _date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y%m%d").date()


def typical_weekday(feed: zipfile.ZipFile) -> dt.date:
    """A quarta-feira mais próxima do meio da validade do GTFS."""
    start, end = feed_window(feed)
    middle = start + (end - start) / 2
    return middle + dt.timedelta(days=(2 - middle.weekday()) % 7)


def _seconds(values: pd.Series) -> pd.Series:
    parts = values.str.split(":", expand=True).reindex(columns=[0, 1, 2])
    hours, minutes, seconds = (pd.to_numeric(parts[c], errors="coerce") for c in (0, 1, 2))
    total: pd.Series = hours * 3600 + minutes * 60 + seconds
    return total


def stop_passes(feed: zipfile.ZipFile, day: dt.date) -> pd.DataFrame:
    """Uma linha por passagem de ônibus em parada, com a hora interpolada."""
    trips = _read(feed, "trips.txt", ["trip_id", "route_id", "service_id"])
    trips = trips[trips["service_id"].isin(active_services(feed, day))]
    times = _read(feed, "stop_times.txt", ["trip_id", "departure_time", "stop_id", "stop_sequence"])
    times = times[times["trip_id"].isin(trips["trip_id"])].copy()
    times["seq"] = times["stop_sequence"].astype(int)
    times["seconds"] = _seconds(times["departure_time"])
    times = times.sort_values(["trip_id", "seq"])
    times["seconds"] = times.groupby("trip_id")["seconds"].transform(
        lambda s: s.interpolate(limit_area="inside")
    )
    times = times.dropna(subset=["seconds"])
    times["hour"] = (np.floor(times["seconds"] / 3600) % 24).astype(int)
    return times.merge(trips[["trip_id", "route_id"]], on="trip_id")


def stops_by_hour(feed_path: Path) -> tuple[pd.DataFrame, dt.date]:
    with zipfile.ZipFile(feed_path) as feed:
        day = typical_weekday(feed)
        passes = stop_passes(feed, day)
        stops = _read(feed, "stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"])
    counts = passes.groupby(["stop_id", "hour"])["trip_id"].nunique().unstack(fill_value=0)
    counts = counts.reindex(columns=range(24), fill_value=0)
    routes = passes.groupby("stop_id")["route_id"].nunique().rename("routes")
    table = stops.set_index("stop_id").join(counts, how="inner").join(routes)
    table["total"] = table[list(range(24))].sum(axis=1)
    return table.reset_index(), day
