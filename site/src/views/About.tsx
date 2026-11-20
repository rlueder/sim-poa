import { SOURCES } from '../sources';

export function About() {
  return (
    <div className="flex max-w-3xl flex-col gap-10">
      <section aria-labelledby="situacao" className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold" id="situacao">
          Em construção
        </h2>
        <p>
          A etapa atual monta o atlas do trânsito observado a partir dos dados públicos da cidade. A
          comparação de cenários (ruas de mão única, estacionamento, cobrança por zona, semáforos)
          vem depois da calibração do modelo.
        </p>
        <p className="text-muted-foreground">
          O modelo serve para comparar cenários entre si, com o erro de calibração declarado. Ele
          não prevê tempos de viagem absolutos em uma rua específica.
        </p>
      </section>

      <section aria-labelledby="fontes" className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold" id="fontes">
          Fontes de dados
        </h2>
        <ul className="flex flex-col gap-3">
          {SOURCES.map((source) => (
            <li key={source.name}>
              <a
                className="text-primary font-medium underline underline-offset-4"
                href={source.href}
                rel="noreferrer"
                target="_blank"
              >
                {source.name}
              </a>
              <p className="text-muted-foreground text-sm">{source.description}</p>
            </li>
          ))}
          <li>
            <a
              className="text-primary font-medium underline underline-offset-4"
              href="https://openfreemap.org/"
              rel="noreferrer"
              target="_blank"
            >
              OpenFreeMap
            </a>
            <p className="text-muted-foreground text-sm">
              Mapa base, © OpenMapTiles, com dados do OpenStreetMap.
            </p>
          </li>
        </ul>
      </section>
    </div>
  );
}
