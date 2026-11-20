from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from sim_poa.atlas.geocode import NEAR_METRES, StreetIndex, split_crossing, street_tokens

# Malha sintética em metros (SIRGAS 2000 / UTM 22S), perto do Centro de Porto Alegre.
X0, Y0 = 480_000.0, 6_677_000.0
CRS = "EPSG:31982"


def _segment(
    name: str, coords: list[tuple[float, float]], numbers: tuple[int, int, int, int]
) -> dict[str, object]:
    odd_from, odd_to, even_from, even_to = numbers
    return {
        "NMIDELOG": name,
        "NRIMPINI": odd_from,
        "NRIMPFIN": odd_to,
        "NRPARINI": even_from,
        "NRPARFIN": even_to,
        "geometry": LineString([(X0 + x, Y0 + y) for x, y in coords]),
    }


@pytest.fixture(scope="module")
def index() -> StreetIndex:
    rows = [
        # Avenida leste-oeste de 0 a 1000 m, numeração crescente para leste.
        _segment("IPIRANGA", [(0, 0), (1000, 0)], (1, 999, 2, 1000)),
        # Rua norte-sul que cruza a avenida em x = 400.
        _segment("CORONEL CLAUDINO", [(400, -300), (400, 300)], (1, 99, 2, 100)),
        # Rua que para 20 m antes da avenida (não toca).
        _segment("GENERAL CAMARA", [(700, 20), (700, 300)], (1, 99, 2, 100)),
        # Rua longe de tudo.
        _segment("BALTAZAR OLIVEIRA GARCIA", [(5000, 5000), (5000, 6000)], (1, 99, 2, 100)),
        _segment("SAO FRANCISCO CALIFORNIA", [(900, -200), (900, 200)], (1, 99, 2, 100)),
    ]
    return StreetIndex(gpd.GeoDataFrame(rows, crs=CRS))


def test_street_tokens_drop_types_and_expand_titles() -> None:
    assert street_tokens("R. Cel. Claudino") == ["CORONEL", "CLAUDINO"]
    assert street_tokens("Av. São Francisco da Califórnia") == ["SAO", "FRANCISCO", "CALIFORNIA"]
    assert street_tokens("Rua") == []


@pytest.mark.parametrize(
    ("site", "parts"),
    [
        ("Av. Ipiranga x R. Cel. Claudino", ["Av. Ipiranga", "R. Cel. Claudino"]),
        ("AV. A X B (CAMERA 054)", ["AV. A", "B"]),
        ("Av. Padre Cacique & Rua C", ["Av. Padre Cacique", "Rua C"]),
        ("Bento Gonçalves com Paulino Azurenha", ["Bento Gonçalves", "Paulino Azurenha"]),
        ("Av.Bernardino Amorim_entre Dona Beca x Amélia", ["Av.Bernardino Amorim", "Dona Beca"]),
        (
            "Nilo Peçanha ENTRE as ruas Dr. Alberto Barbosa e Viela",
            ["Nilo Peçanha", "Dr. Alberto Barbosa"],
        ),
    ],
)
def test_split_crossing(site: str, parts: list[str]) -> None:
    assert split_crossing(site) == parts


def test_crossing_is_located_and_reprojected(index: StreetIndex) -> None:
    loc = index.locate("Av. Ipiranga x R. Cel. Claudino (veic)")
    assert loc.ok and loc.method == "cruzamento"
    assert loc.streets == "IPIRANGA x CORONEL CLAUDINO"
    assert loc.lat is not None and -30.1 < loc.lat < -29.9


def test_initials_and_near_miss(index: StreetIndex) -> None:
    assert index.match("Baltazar de O. Garcia") == "BALTAZAR OLIVEIRA GARCIA"
    near = index.locate("Ipiranga x Gen. Câmara")
    assert near.ok and near.method == "proximidade"
    assert NEAR_METRES >= 20


def test_failures_say_why(index: StreetIndex) -> None:
    assert "não encontrada" in index.locate("Ipiranga x Rua Inexistente").reason
    assert "não se cruzam" in index.locate("Ipiranga x Baltazar Garcia").reason
    assert "mesma" in index.locate("Ipiranga x Av. Ipiranga").reason
    assert "sem cruzamento" in index.locate("Av. Ipiranga").reason


def test_address_is_interpolated_on_the_matching_parity(index: StreetIndex) -> None:
    east = index.locate("Av. Ipiranga, nº 800 (escola)")
    west = index.locate("Av. Ipiranga, 200")
    assert east.ok and east.method == "endereço"
    assert west.lon is not None and east.lon is not None and west.lon < east.lon
    assert "fora das faixas" in index.locate("Av. Ipiranga, 5000").reason


def test_between_streets_uses_the_first_crossing(index: StreetIndex) -> None:
    loc = index.locate("Av. Ipiranga entre as ruas Cel. Claudino e São Francisco da Califórnia")
    assert loc.ok and loc.method == "trecho"
    assert loc.streets == "IPIRANGA x CORONEL CLAUDINO"
