"""Leitura de valores de planilhas que o Excel converteu de forma enganosa."""

from __future__ import annotations

import datetime as dt
import math

# O Excel conta 1900 como ano bissexto: o serial 60 é o inexistente 29/02/1900.
# Abaixo dele, o dia 1 é 01/01/1900; a partir do 61, a conta usual com época
# em 30/12/1899 acerta. Converter tudo pela época usual desloca em um os
# códigos pequenos que a planilha formatou como data.
_EPOCH_BEFORE_LEAP_BUG = dt.datetime(1899, 12, 31)
_EPOCH = dt.datetime(1899, 12, 30)
_LEAP_BUG_SERIAL = 60


def excel_serial(value: dt.datetime) -> float:
    """Número serial do Excel por trás de uma data lida pelo openpyxl."""
    days = (value - _EPOCH_BEFORE_LEAP_BUG).days
    base = _EPOCH_BEFORE_LEAP_BUG if days < _LEAP_BUG_SERIAL else _EPOCH
    delta = value - base
    return delta.days + delta.seconds / 86400


def as_number(value: object) -> float | None:
    """Número de uma célula, desfazendo a conversão para data quando houver."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dt.datetime):
        return excel_serial(value)
    if isinstance(value, int | float):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text or text.upper() in {"NA", "--", "-"}:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def as_code(value: object) -> int | None:
    number = as_number(value)
    if number is None:
        return None
    if number != int(number):
        raise ValueError(f"código não inteiro: {value!r}")
    return int(number)


def minutes_of_day(value: object) -> int | None:
    """Minutos desde a meia-noite de um horário (`time`, data com hora ou `HH:MM`)."""
    if isinstance(value, dt.datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, dt.time):
        return value.hour * 60 + value.minute
    if isinstance(value, str) and ":" in value:
        hours, minutes = value.strip().split(":")[:2]
        return int(hours) * 60 + int(minutes)
    return None
