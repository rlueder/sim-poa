import { ChartContainer, type ChartContainerProps } from '@precisa-saude/ui/charts';
import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  type CountSurvey,
  loadProfile,
  profilePoints,
  type QuarterProfile,
  SUBJECT_LABELS,
} from '../../data/counts';
import { formatClock, formatInteger } from '../../data/format';
import { CATEGORICAL, INK } from '../../viz/palette';

const Responsive = ResponsiveContainer as unknown as ChartContainerProps['ResponsiveContainer'];

const FLAG_LABELS: Record<string, string> = {
  '24h': 'contagem de 24 horas',
  'data-diverge-do-nome': 'a data da planilha difere da do nome do arquivo',
  'fim-de-semana': 'fim de semana',
  incompleta: 'pesquisa incompleta',
  'so-picos': 'só nos picos',
};

export function SurveyDetail({ survey }: { survey: CountSurvey }) {
  const [profile, setProfile] = useState<null | QuarterProfile | undefined>(null);

  useEffect(() => {
    setProfile(null);
    if (survey.year === null) {
      setProfile(undefined);
      return;
    }
    loadProfile(survey.year, survey.id).then(setProfile, () => setProfile(undefined));
  }, [survey]);

  const rows = profile ? profilePoints(profile) : [];
  return (
    <article className="border-border flex flex-col gap-3 rounded-lg border p-4">
      <header>
        <h3 className="font-semibold">{survey.name}</h3>
        <p className="text-muted-foreground text-sm">
          {SUBJECT_LABELS[survey.subject]} · {survey.date || survey.year} · localizado por{' '}
          {survey.located_by}
          {survey.corridors.length > 0 && ` · ${survey.corridors.join(', ')}`}
        </p>
        {survey.flags.length > 0 && (
          <p className="text-sm">
            Atenção: {survey.flags.map((f) => FLAG_LABELS[f] ?? f).join('; ')}.
          </p>
        )}
      </header>
      {profile === null && <p aria-busy="true">Carregando o perfil…</p>}
      {profile === undefined && (
        <p className="text-muted-foreground text-sm">
          Esta pesquisa não tem intervalos de 15 minutos; os totais por hora estão no relatório.
        </p>
      )}
      {profile && (
        <figure className="flex flex-col gap-2">
          <figcaption className="text-sm font-medium">
            Total de todos os movimentos e classes, a cada 15 minutos
          </figcaption>
          <ChartContainer height={220} ResponsiveContainer={Responsive}>
            <LineChart data={rows} margin={{ bottom: 0, left: 8, right: 16, top: 8 }}>
              <CartesianGrid stroke="#e1e0d9" vertical={false} />
              <XAxis
                dataKey="start"
                domain={['dataMin', 'dataMax']}
                stroke={INK.muted}
                tickFormatter={(v: number) => formatClock(v)}
                type="number"
              />
              <YAxis
                stroke={INK.muted}
                tickFormatter={(v: number) => formatInteger(v)}
                width={56}
              />
              <Tooltip
                formatter={(value) => [formatInteger(Number(value)), 'contagem']}
                labelFormatter={(label) =>
                  `${formatClock(Number(label))} a ${formatClock(Number(label) + 15)}`
                }
              />
              <Line
                connectNulls={false}
                dataKey="count"
                dot={false}
                isAnimationActive={false}
                stroke={CATEGORICAL[0]}
                strokeWidth={2}
                type="linear"
              />
            </LineChart>
          </ChartContainer>
          <details className="text-sm">
            <summary className="cursor-pointer">Ver tabela</summary>
            <table className="mt-2 w-full tabular-nums">
              <thead>
                <tr className="text-muted-foreground text-left">
                  <th scope="col">Início</th>
                  <th className="text-right" scope="col">
                    Contagem
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.start}>
                    <th className="text-left font-normal" scope="row">
                      {formatClock(row.start)}
                    </th>
                    <td className="text-right">
                      {row.count === null ? 'sem dado' : formatInteger(row.count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </figure>
      )}
    </article>
  );
}
