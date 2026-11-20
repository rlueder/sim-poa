export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${path}`);
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${path}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export interface Attribution {
  href: string;
  name: string;
}

export interface FileSummary {
  by_status: Record<string, number>;
  files: number;
  read_and_located: number;
  unread_reasons?: Record<string, number>;
}

/** Métodos de localização agrupados em dois níveis de confiança, para conferência no mapa. */
export const EXACT_METHODS = new Set(['cruzamento', 'endereço']);

export const FOCUS_CORRIDORS = [
  'Av. Carlos Gomes',
  'Av. Protásio Alves',
  'Av. Ipiranga',
  'Av. Nilo Peçanha / Av. Nilópolis',
] as const;
