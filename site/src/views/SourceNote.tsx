export interface SourceLink {
  href: string;
  label: string;
}

/** Fontes de uma visualização. Toda visualização com dados da EPTC mostra a atribuição. */
export function SourceNote({ sources }: { sources: SourceLink[] }) {
  return (
    <footer className="border-border text-muted-foreground border-t pt-3 text-xs">
      <span className="font-medium">Fonte{sources.length > 1 ? 's' : ''}: </span>
      {sources.map((source, i) => (
        <span key={source.href + source.label}>
          {i > 0 && '; '}
          <a
            className="underline underline-offset-2"
            href={source.href}
            rel="noreferrer"
            target="_blank"
          >
            {source.label}
          </a>
        </span>
      ))}
      . Mapa base: OpenFreeMap, © OpenMapTiles, dados © colaboradores do OpenStreetMap.
    </footer>
  );
}
