import { SlidingTabs } from '@precisa-saude/ui/navigation';
import { useEffect, useState } from 'react';

import { type EdomData, loadEdom, type Measure } from '../../data/edom';
import { formatHourRange, formatInteger } from '../../data/format';
import { SourceNote } from '../SourceNote';
import { ProfileChart } from './ProfileChart';
import { MAX_LINES } from './shared';
import { TripsMap } from './TripsMap';
import { ValidationTable } from './ValidationTable';

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export function TripsView() {
  const [data, setData] = useState<EdomData | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [measure, setMeasure] = useState<Measure>('produced');
  const [hour, setHour] = useState<null | number>(null);
  const [showLines, setShowLines] = useState(true);

  useEffect(() => {
    loadEdom().then(setData, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data) return <p aria-busy="true">Carregando a pesquisa de origem e destino…</p>;

  return (
    <section aria-labelledby="viagens-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="viagens-titulo">
          Viagens dos moradores
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Pesquisa domiciliar de origem e destino de 2023: cerca de 10 mil domicílios entrevistados
          entre agosto de 2023 e abril de 2024, expandidos para todos os moradores. Os números são
          viagens em um dia útil, agregadas por zona de tráfego.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <SlidingTabs
          activeKey={measure}
          aria-label="Viagens por origem ou destino"
          items={[
            { key: 'produced', label: 'Origem' },
            { key: 'attracted', label: 'Destino' },
          ]}
          size="sm"
          onChange={(key) => setMeasure(key as Measure)}
        />
        <label className="flex items-center gap-2 text-sm">
          Horário
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={hour ?? ''}
            onChange={(e) => setHour(e.target.value === '' ? null : Number(e.target.value))}
          >
            <option value="">Dia todo</option>
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {formatHourRange(h)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            checked={showLines}
            type="checkbox"
            onChange={(e) => setShowLines(e.target.checked)}
          />
          Linhas de desejo
        </label>
      </div>

      <TripsMap data={data} hour={hour} measure={measure} showLines={showLines} />
      <p className="text-muted-foreground text-xs">
        As cores mostram as viagens {measure === 'produced' ? 'que saem de' : 'que chegam a'} cada
        zona{hour === null ? ' no dia todo' : `, ${formatHourRange(hour)}`}. As linhas ligam os{' '}
        {formatInteger(MAX_LINES)} maiores fluxos entre zonas no dia todo, com espessura
        proporcional ao número de viagens; só entram pares com pelo menos {data.lines.min_records}{' '}
        entrevistas na amostra.
      </p>

      <ProfileChart profile={data.profile} />
      <ValidationTable checks={data.validation.checks} />
      <SourceNote
        sources={[
          {
            href: data.validation.source.href,
            label: `${data.validation.source.name}: ${data.validation.source.dataset}`,
          },
        ]}
      />
    </section>
  );
}
