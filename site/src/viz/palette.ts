// Cores de dados. As cores de gráfico do pacote de temas foram reprovadas no
// validador de paletas (faixa de luminosidade, croma e um par adjacente
// indistinguível), então os dados usam a paleta de referência validada; a
// interface continua com os tokens do tema. Validado em 20/11/2026 contra o
// fundo #efeae6: quatro séries em linha (pares adjacentes) e três em mapa
// (todos os pares). Três cores ficam abaixo de 3:1 de contraste, o que exige
// rótulos diretos ou a tabela, e os gráficos oferecem os dois.

export const CATEGORICAL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'] as const;

// Rampa sequencial de um só matiz, do claro ao escuro (passos 150 a 650).
export const SEQUENTIAL = [
  '#b7d3f6',
  '#86b6ef',
  '#5598e7',
  '#2a78d6',
  '#1c5cab',
  '#104281',
] as const;

// Escala divergente: azul abaixo do limite, cinza neutro no meio, vermelho acima. O braço
// vermelho tem as mesmas luminosidades OKLCH do azul (passos 250, 450 e 650) com o matiz
// do vermelho da paleta de referência, para os dois lados pesarem igual.
export const DIVERGING = [
  '#104281',
  '#2a78d6',
  '#86b6ef',
  '#c3c2b7',
  '#f2958e',
  '#d2383a',
  '#7e1519',
] as const;

export const INK = {
  muted: '#898781',
  primary: '#0b0b0b',
  secondary: '#52514e',
} as const;

export const NO_DATA = '#e1e0d9';
