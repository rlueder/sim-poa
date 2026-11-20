# sim-poa

Simulação aberta do trânsito de Porto Alegre, construída com dados públicos e ferramentas de código aberto.

_Open traffic simulation of Porto Alegre, built from public data with open-source tools._

## Objetivo

1. **Ver a cidade real.** Mapas e gráficos do trânsito observado: volumes, velocidades, padrões de viagem, sinistros, ônibus e estacionamento.
2. **Testar intervenções.** Alterar a rede ou as regras e comparar com um cenário de referência: ruas de mão única, mudanças no estacionamento, cobrança para entrar em uma zona, ajuste de semáforos.

O modelo serve para comparar cenários entre si, com o erro de calibração declarado. Ele não prevê tempos de viagem absolutos em uma rua específica.

## Situação

O projeto está no início. Já existe o download reproduzível dos dados brutos; ainda não há código de simulação. O plano, as fontes de dados verificadas e os critérios de aceite de cada fase estão em [`docs/development/IMPLEMENTATION_GUIDE.md`](docs/development/IMPLEMENTATION_GUIDE.md) (em inglês), e o andamento em [`docs/development/PLAN.md`](docs/development/PLAN.md).

## Como rodar

Requisitos: Node 22 ou mais recente, pnpm 9 e [uv](https://docs.astral.sh/uv/). O uv instala o Python 3.13 e o SUMO 1.28.0 sozinho.

```bash
pnpm install
pnpm test                          # testes do pipeline e do site
pnpm data:fetch                    # baixa cerca de 3 GB de dados públicos para data/raw/
pnpm data:fetch --group centro     # opcional: estudo completo do Centro Histórico (8,6 GB)
pnpm --filter @sim-poa/site dev    # site local
```

O primeiro `pnpm data:fetch` leva algumas horas: são cerca de 5.700 arquivos baixados um de cada vez, com uma pausa entre eles, para não sobrecarregar os servidores da Prefeitura. Cada arquivo baixado fica registrado em `data/manifest.csv`, com URL, tamanho e SHA-256; uma segunda execução só baixa o que mudou no servidor.

## Como funciona

- **Simulador:** [Eclipse SUMO](https://eclipse.dev/sumo/), em modo mesoscópico para a cidade inteira e microscópico em recortes.
- **Demanda:** pesquisa domiciliar de origem e destino EDOM 2023, corrigida com contagens de veículos da EPTC.
- **Rede viária:** OpenStreetMap.
- **Visualização:** site estático em React.

## Fontes de dados e atribuição

- **EPTC (Empresa Pública de Transporte e Circulação), Prefeitura de Porto Alegre:** pesquisa EDOM, contagens, pesquisas de velocidade, cadastro de semáforos, Área Azul, sinistros e transporte coletivo, publicados pelo [ObservaMOB](https://prefeitura.poa.br/eptc/projetos/observamob) e pelo [portal de dados abertos](https://dadosabertos.poa.br/).
- **OpenStreetMap:** © colaboradores do OpenStreetMap, sob a licença [ODbL](https://www.openstreetmap.org/copyright).
- **IBGE:** Censo Demográfico 2022.

Este projeto não tem vínculo com a EPTC nem com a Prefeitura de Porto Alegre.

## Licença

Código sob a licença [MIT](LICENSE). Os dados seguem os termos de cada fonte.
