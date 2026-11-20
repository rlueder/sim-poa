"""Velocidade padrão por classe de via, para vias sem `maxspeed` no OSM.

Código de Trânsito Brasileiro (Lei nº 9.503, de 23 de setembro de 1997),
art. 61, § 1º, I: onde não existir sinalização regulamentadora, a velocidade
máxima nas vias urbanas é de 80 km/h nas vias de trânsito rápido, 60 km/h nas
arteriais, 40 km/h nas coletoras e 30 km/h nas locais. Texto lido em
https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm em 20/11/2026.

A correspondência entre as classes do OSM e as do art. 60 é uma premissa deste
projeto, registrada em docs/ASSUMPTIONS.md.
"""

from __future__ import annotations

CTB_URBAN_KMH = {
    "transito_rapido": 80.0,
    "arterial": 60.0,
    "coletora": 40.0,
    "local": 30.0,
}

OSM_TO_CTB = {
    "motorway": "transito_rapido",
    "motorway_link": "transito_rapido",
    "trunk": "transito_rapido",
    "trunk_link": "transito_rapido",
    "primary": "arterial",
    "primary_link": "arterial",
    "secondary": "arterial",
    "secondary_link": "arterial",
    "tertiary": "coletora",
    "tertiary_link": "coletora",
    "unclassified": "local",
    "residential": "local",
    "living_street": "local",
}


def default_speeds_kmh() -> dict[str, float]:
    return {highway: CTB_URBAN_KMH[ctb] for highway, ctb in OSM_TO_CTB.items()}
