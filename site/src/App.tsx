import { SOURCES } from './sources';

export function App() {
  return (
    <div className="bg-background text-foreground min-h-screen">
      <main className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-16">
        <header className="flex flex-col gap-3">
          <h1 className="text-4xl font-semibold tracking-tight">sim-poa</h1>
          <p className="text-muted-foreground text-lg">
            Simulação aberta do trânsito de Porto Alegre, construída com dados públicos e
            ferramentas de código aberto.
          </p>
        </header>

        <section aria-labelledby="situacao" className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold" id="situacao">
            Em construção
          </h2>
          <p>
            A etapa atual reúne os dados públicos de trânsito da cidade. Os mapas do trânsito
            observado entram aqui na etapa seguinte, e a comparação de cenários (ruas de mão única,
            estacionamento, cobrança por zona, semáforos) depois da calibração do modelo.
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
          </ul>
          <p className="text-muted-foreground text-sm">
            Este projeto não tem vínculo com a EPTC nem com a Prefeitura de Porto Alegre.
          </p>
        </section>

        <footer className="border-border text-muted-foreground border-t pt-6 text-sm">
          Código aberto sob a licença MIT em{' '}
          <a
            className="underline underline-offset-4"
            href="https://github.com/rlueder/sim-poa"
            rel="noreferrer"
            target="_blank"
          >
            github.com/rlueder/sim-poa
          </a>
          .
        </footer>
      </main>
    </div>
  );
}
