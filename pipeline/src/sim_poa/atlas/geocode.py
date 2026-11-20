"""Localização de pontos de pesquisa pelo nome do cruzamento.

As planilhas de contagem identificam o local como "Rua A x Rua B". O ponto é
a interseção das duas vias nos eixos de logradouros da EPTC, depois de
normalizar abreviações e títulos. Quando as vias não se tocam no traçado,
aceita-se a menor distância entre elas até `NEAR_METRES` (praças são
desenhadas pelo contorno e ficam a dezenas de metros do eixo da rua), com o
método registrado como "proximidade". Pontos no meio da quadra ("Av. X entre
A x B") ficam no cruzamento de X com A, como "trecho". Endereços ("Av. X,
nº 1545") são interpolados ao longo do segmento cuja faixa de numeração
contém o número, como "endereço"; se nenhuma faixa contém o número (a
numeração dos eixos tem lacunas, e em avenidas duplas um lado vem zerado),
vale o trecho numerado mais próximo, até `ADDRESS_SLACK` números de
distância, como "endereço-aproximado". O que não se resolve fica listado com
o motivo.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union

NEAR_METRES = 50.0
FUZZY_CUTOFF = 0.86
ADDRESS_SLACK = 300

# Tipos de logradouro: tirados do nome antes de comparar.
_TYPES = {
    "AV",
    "AVENIDA",
    "R",
    "RUA",
    "EST",
    "ESTR",
    "ESTRADA",
    "TRAV",
    "TV",
    "TRAVESSA",
    "AL",
    "ALAMEDA",
    "PCA",
    "PC",
    "PRACA",
    "LG",
    "LARGO",
    "VD",
    "VIADUTO",
    "ROD",
    "RODOVIA",
    "PSG",
    "PASSAGEM",
    "BC",
    "BECO",
    "ACESSO",
    "AC",
    "VIA",
    "PQ",
    "PARQUE",
    "TUNEL",
    "PONTE",
}
# Títulos abreviados nas planilhas e escritos por extenso nos eixos.
_TITLES = {
    "CEL": "CORONEL",
    "GEN": "GENERAL",
    "DR": "DOUTOR",
    "DRA": "DOUTORA",
    "PE": "PADRE",
    "STA": "SANTA",
    "STO": "SANTO",
    "S": "SAO",
    "PROF": "PROFESSOR",
    "PROFA": "PROFESSORA",
    "ENG": "ENGENHEIRO",
    "DES": "DESEMBARGADOR",
    "MAL": "MARECHAL",
    "MAJ": "MAJOR",
    "CAP": "CAPITAO",
    "TEN": "TENENTE",
    "SGT": "SARGENTO",
    "ALM": "ALMIRANTE",
    "BRIG": "BRIGADEIRO",
    "PRES": "PRESIDENTE",
    "VER": "VEREADOR",
    "DEP": "DEPUTADO",
    "SEN": "SENADOR",
    "GOV": "GOVERNADOR",
    "BAR": "BARAO",
    "VISC": "VISCONDE",
    "CONS": "CONSELHEIRO",
    "D": "DOM",
    "FR": "FREI",
    "IR": "IRMAO",
    "MONS": "MONSENHOR",
    "COM": "COMENDADOR",
    "JORN": "JORNALISTA",
    "ARQ": "ARQUITETO",
    "MIN": "MINISTRO",
}
_STOP = {"DA", "DE", "DO", "DAS", "DOS", "E"}
_SPLIT = re.compile(r"\s+(?:x|X|&|com|COM|esq\.?|ESQ\.?|esquina|ESQUINA)\s+|\s*\bx\b\s*")
_NOISE = re.compile(
    r"\(.*?\)|_(?!entre).*$|\bn[ºo°]\s*\d+\b|\bCAM(?:ERA)?\s*\d+\b|-\s*(?:s[aá]bado|domingo).*$",
    re.IGNORECASE,
)


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def street_tokens(name: str) -> list[str]:
    """Palavras significativas de um nome de via, com títulos por extenso."""
    words = re.findall(r"[A-Z0-9]+", fold(name).replace(".", " "))
    while words and words[0] in _TYPES:
        words = words[1:]
    return [_TITLES.get(w, w) for w in words if w not in _STOP]


_BETWEEN = re.compile(r"[\s_]+entre\s+(?:as\s+ruas\s+|a\s+rua\s+)?", re.IGNORECASE)
_ADDRESS = re.compile(
    r"^(?P<street>.+?)[\s,]+n?[ºo°]?\s*\.?\s*(?P<number>\d{1,5})\b", re.IGNORECASE
)
# Expressões de aproximação nos nomes ("próx. ao 7712", "Altura 1200").
_APPROX = re.compile(
    r"\b(?:pr[oó]x(?:imo|\.)?\s*(?:ao|a|do|da)?(?:\s*n[uú]mero)?|altura(?:\s*do|\s*da)?|"
    r"quase\s+em\s+frente\s+(?:ao|a)|em\s+frente\s+(?:ao|a)|defronte(?:\s+ao)?|df)\b\.?",
    re.IGNORECASE,
)
# Faixa de numeração ("entre 900 e 1300"): vale o meio.
_RANGE = re.compile(r"\bentre\s+(\d{1,5})\s+e\s+(\d{1,5})\b", re.IGNORECASE)
_AND = re.compile(r"\s+e\s+", re.IGNORECASE)


def split_crossing(site: str) -> list[str]:
    """Vias de um nome de ponto; em "X entre A x B", devolve X e A."""
    site = re.sub(r"\(\s*(entre\s+[^)]*)\)", r" \1", site, flags=re.IGNORECASE)
    main, between = _split_between(site)
    if between:
        first_cross = _AND.split(between, maxsplit=1)[0]
        crossings = split_crossing(first_cross) or [first_cross]
        return [p for p in (split_crossing(main) or [main]) + crossings[:1] if p][:2]
    cleaned = _NOISE.sub(" ", site).strip(" -")
    parts = [p.strip(" .,-") for p in _SPLIT.split(cleaned) if p and p.strip(" .,-")]
    return [p for p in parts if street_tokens(p)]


def _split_between(site: str) -> tuple[str, str]:
    parts = _BETWEEN.split(site, maxsplit=1)
    return (parts[0], parts[1]) if len(parts) == 2 else (site, "")


@dataclass(frozen=True)
class Location:
    lon: float | None
    lat: float | None
    method: str
    streets: str
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.lon is not None


class StreetIndex:
    """Eixos agrupados por via, com busca por nome normalizado."""

    def __init__(self, centrelines: gpd.GeoDataFrame) -> None:
        lines = centrelines.dropna(subset=["NMIDELOG"])
        self.crs = lines.crs
        grouped: dict[str, list[BaseGeometry]] = {}
        for name, geometry in zip(lines["NMIDELOG"], lines.geometry, strict=True):
            key = " ".join(street_tokens(str(name)))
            if key:
                grouped.setdefault(key, []).append(geometry)
        self.geometry = {key: unary_union(parts) for key, parts in grouped.items()}
        # Faixas de numeração por segmento, para localizar endereços.
        self.segments: dict[str, list[tuple[int, int, int, int, BaseGeometry]]] = {}
        numbered = lines.dropna(subset=["NRIMPINI", "NRIMPFIN", "NRPARINI", "NRPARFIN"])
        for row in numbered.itertuples():
            key = " ".join(street_tokens(str(row.NMIDELOG)))
            self.segments.setdefault(key, []).append(
                (
                    int(row.NRIMPINI),
                    int(row.NRIMPFIN),
                    int(row.NRPARINI),
                    int(row.NRPARFIN),
                    row.geometry,
                )
            )
        self.names = sorted(self.geometry)
        self._by_token: dict[str, set[str]] = {}
        for key in self.names:
            for token in key.split():
                self._by_token.setdefault(token, set()).add(key)

    def _with_token(self, token: str) -> set[str]:
        if len(token) > 1:
            return self._by_token.get(token, set())
        found: set[str] = set()
        for known, keys in self._by_token.items():
            if known.startswith(token):
                found |= keys
        return found

    @classmethod
    def from_zip(cls, path: Path) -> StreetIndex:
        return cls(gpd.read_file(f"zip://{path}"))

    def match(self, name: str) -> str | None:
        tokens = street_tokens(name)
        if not tokens:
            return None
        key = " ".join(tokens)
        if key in self.geometry:
            return key
        # Todas as palavras da consulta aparecem no nome: vale o nome mais curto.
        # Iniciais ("Baltazar de O. Garcia") casam com qualquer palavra que comece pela letra.
        candidates = set.intersection(*(self._with_token(t) for t in tokens))
        if candidates:
            return min(candidates, key=lambda k: (len(k), k))
        close = difflib.get_close_matches(key, self.names, n=1, cutoff=FUZZY_CUTOFF)
        return close[0] if close else None

    def locate_address(self, street: str, number: int) -> Location | None:
        key = self.match(street)
        if key is None:
            return None
        ranges: list[tuple[int, int, BaseGeometry]] = []
        for odd_from, odd_to, even_from, even_to, geometry in self.segments.get(key, []):
            # Mesmo lado da rua primeiro; o outro lado serve quando este vem zerado.
            same, other = (odd_from, odd_to), (even_from, even_to)
            if number % 2 == 0:
                same, other = other, same
            for start, end in (same, other):
                if start or end:
                    ranges.append((start, end, geometry))
                    break
        best: tuple[int, int, int, BaseGeometry] | None = None
        for start, end, geometry in ranges:
            low, high = min(start, end), max(start, end)
            gap = 0 if low <= number <= high else min(abs(number - low), abs(number - high))
            if best is None or gap < best[0]:
                best = (gap, start, end, geometry)
        if best is None or best[0] > ADDRESS_SLACK:
            return None
        gap, start, end, geometry = best
        low, high = min(start, end), max(start, end)
        share = 0.5 if high == low else (min(max(number, low), high) - low) / (high - low)
        point = geometry.interpolate(share if start <= end else 1 - share, normalized=True)
        method = "endereço" if gap == 0 else "endereço-aproximado"
        return self._to_wgs84(point, method, f"{key}, {number}")

    def locate(self, site: str) -> Location:
        parts = split_crossing(site)
        if len(parts) < 2:
            # Aqui o número importa: só saem os parênteses, o sufixo depois de "_"
            # e expressões de aproximação ("próx. ao 7712").
            plain = _APPROX.sub(" ", re.sub(r"\(.*?\)|_.*$", " ", site))
            plain = _RANGE.sub(lambda m: str((int(m.group(1)) + int(m.group(2))) // 2), plain)
            address = _ADDRESS.match(re.sub(r"\s+", " ", plain).strip(" ,"))
            if address:
                found = self.locate_address(address.group("street"), int(address.group("number")))
                if found is not None:
                    return found
                return Location(None, None, "", site, "endereço fora das faixas de numeração")
            return Location(None, None, "", site, "nome sem cruzamento identificável")
        keys = [self.match(p) for p in parts[:2]]
        missing = [p for p, k in zip(parts, keys, strict=False) if k is None]
        if missing:
            return Location(None, None, "", site, f"via não encontrada: {'; '.join(missing)}")
        a, b = (self.geometry[k] for k in keys if k is not None)
        streets = " x ".join(k for k in keys if k)
        between = bool(_split_between(site)[1])
        if keys[0] == keys[1]:
            return Location(None, None, "", streets, "as duas vias são a mesma")
        crossing = a.intersection(b)
        if not crossing.is_empty:
            point = crossing if crossing.geom_type == "Point" else crossing.centroid
            method = "cruzamento" if crossing.geom_type == "Point" else "cruzamento-multiplo"
            if between:
                method = "trecho"
            return self._to_wgs84(point, method, streets)
        pa, pb = nearest_points(a, b)
        gap = pa.distance(pb)
        if gap <= NEAR_METRES:
            midpoint = Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)
            return self._to_wgs84(midpoint, "proximidade", streets)
        return Location(None, None, "", streets, f"vias não se cruzam (distância {gap:.0f} m)")

    def _to_wgs84(self, point: BaseGeometry, method: str, streets: str) -> Location:
        lonlat = gpd.GeoSeries([point], crs=self.crs).to_crs(4326).iloc[0]
        return Location(round(lonlat.x, 6), round(lonlat.y, 6), method, streets)
