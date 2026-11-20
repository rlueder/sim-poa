export interface Source {
  description: string;
  href: string;
  name: string;
}

export const SOURCES: Source[] = [
  {
    description:
      'Pesquisa domiciliar de origem e destino (EDOM 2023), contagens de veículos, pesquisas de velocidade, semáforos, Área Azul, sinistros e transporte coletivo.',
    href: 'https://prefeitura.poa.br/eptc/projetos/observamob',
    name: 'EPTC, Prefeitura de Porto Alegre (ObservaMOB)',
  },
  {
    description: 'GTFS, tabelas horárias e inventário de sinalização.',
    href: 'https://dadosabertos.poa.br/',
    name: 'Portal de dados abertos de Porto Alegre',
  },
  {
    description: 'Rede viária. © colaboradores do OpenStreetMap, licença ODbL.',
    href: 'https://www.openstreetmap.org/copyright',
    name: 'OpenStreetMap',
  },
  {
    description: 'Censo Demográfico 2022, microdados da amostra.',
    href: 'https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Microdados_e_Areas_de_Ponderacao/',
    name: 'IBGE',
  },
];
