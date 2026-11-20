import { SlidingTabs } from '@precisa-saude/ui/navigation';
import { lazy, Suspense, useEffect, useState } from 'react';

// Cada visualização vira um pedaço separado do bundle: quem abre só a aba Sobre não
// baixa o MapLibre nem o recharts.
const About = lazy(() => import('./views/About').then((m) => ({ default: m.About })));
const BusesView = lazy(() =>
  import('./views/buses/BusesView').then((m) => ({ default: m.BusesView })),
);
const CountsView = lazy(() =>
  import('./views/counts/CountsView').then((m) => ({ default: m.CountsView })),
);
const CrashesView = lazy(() =>
  import('./views/crashes/CrashesView').then((m) => ({ default: m.CrashesView })),
);
const SpeedsView = lazy(() =>
  import('./views/speeds/SpeedsView').then((m) => ({ default: m.SpeedsView })),
);
const SupplyView = lazy(() =>
  import('./views/supply/SupplyView').then((m) => ({ default: m.SupplyView })),
);
const TripsView = lazy(() =>
  import('./views/trips/TripsView').then((m) => ({ default: m.TripsView })),
);

const VIEWS = [
  { key: 'viagens', label: 'Viagens' },
  { key: 'contagens', label: 'Contagens' },
  { key: 'velocidades', label: 'Velocidades' },
  { key: 'onibus', label: 'Ônibus' },
  { key: 'oferta', label: 'Oferta' },
  { key: 'sinistros', label: 'Sinistros' },
  { key: 'sobre', label: 'Sobre' },
] as const;

type ViewKey = (typeof VIEWS)[number]['key'];

function viewFromHash(): ViewKey {
  const key = window.location.hash.replace('#', '');
  return VIEWS.some((v) => v.key === key) ? (key as ViewKey) : 'viagens';
}

export function App() {
  const [view, setView] = useState<ViewKey>(viewFromHash);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const select = (key: string) => {
    window.location.hash = key;
    setView(key as ViewKey);
  };

  return (
    <div className="bg-background text-foreground min-h-screen">
      <main className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-10">
        <header className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-3xl font-semibold tracking-tight">sim-poa</h1>
            <p className="text-muted-foreground">
              Atlas do trânsito observado em Porto Alegre, com dados públicos.
            </p>
          </div>
          <nav aria-label="Visualizações">
            <SlidingTabs
              activeKey={view}
              aria-label="Visualizações"
              items={[...VIEWS]}
              onChange={select}
            />
          </nav>
        </header>

        <Suspense fallback={<p aria-busy="true">Carregando…</p>}>
          {view === 'viagens' && <TripsView />}
          {view === 'contagens' && <CountsView />}
          {view === 'velocidades' && <SpeedsView />}
          {view === 'onibus' && <BusesView />}
          {view === 'oferta' && <SupplyView />}
          {view === 'sinistros' && <CrashesView />}
          {view === 'sobre' && <About />}
        </Suspense>

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
          . Este projeto não tem vínculo com a EPTC nem com a Prefeitura de Porto Alegre.
        </footer>
      </main>
    </div>
  );
}
