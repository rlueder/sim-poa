import { ChartContainer, type ChartContainerProps } from '@precisa-saude/ui/charts';
import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { type ProfileFile, PURPOSE_LABELS, PURPOSE_ORDER } from '../../data/edom';
import { formatClock, formatInteger } from '../../data/format';
import { CATEGORICAL, INK } from '../../viz/palette';
import { profileRows } from './profile';

// O ResponsiveContainer do recharts tem tipos de ref que o ChartContainer não declara.
const Responsive = ResponsiveContainer as unknown as ChartContainerProps['ResponsiveContainer'];

export function ProfileChart({ profile }: { profile: ProfileFile }) {
  const rows = useMemo(() => profileRows(profile), [profile]);
  const [showTable, setShowTable] = useState(false);
  const purposes = PURPOSE_ORDER.filter((p) => profile.series[p]);

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">Partidas ao longo do dia, por motivo</span>
        <button
          className="text-primary text-sm underline underline-offset-4"
          type="button"
          onClick={() => setShowTable((v) => !v)}
        >
          {showTable ? 'Ver gráfico' : 'Ver tabela'}
        </button>
      </figcaption>
      {showTable ? (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-sm tabular-nums">
            <caption className="sr-only">
              Viagens expandidas que partem na hora seguinte a cada horário, por motivo
            </caption>
            <thead>
              <tr className="text-muted-foreground text-left">
                <th scope="col">Início</th>
                {purposes.map((p) => (
                  <th key={p} className="text-right" scope="col">
                    {PURPOSE_LABELS[p] ?? p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.slot}>
                  <th className="text-left font-normal" scope="row">
                    {formatClock(row.slot)}
                  </th>
                  {purposes.map((p) => (
                    <td key={p} className="text-right">
                      {formatInteger(row[p] ?? 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ChartContainer height={300} ResponsiveContainer={Responsive}>
          <LineChart data={rows} margin={{ bottom: 0, left: 8, right: 24, top: 8 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis
              dataKey="slot"
              domain={[0, 1425]}
              stroke={INK.muted}
              tickFormatter={(v: number) => formatClock(v)}
              ticks={[0, 240, 480, 720, 960, 1200]}
              type="number"
            />
            <YAxis stroke={INK.muted} tickFormatter={(v: number) => formatInteger(v)} width={64} />
            <Tooltip
              formatter={(value, name) => [
                formatInteger(Number(value)),
                PURPOSE_LABELS[String(name)] ?? String(name),
              ]}
              labelFormatter={(label) =>
                `Partidas entre ${formatClock(Number(label))} e ${formatClock(Number(label) + profile.window_minutes)}`
              }
            />
            <Legend
              formatter={(value: string) => (
                <span style={{ color: INK.secondary }}>{PURPOSE_LABELS[value] ?? value}</span>
              )}
              itemSorter={(item) => PURPOSE_ORDER.indexOf(String(item.dataKey))}
            />
            {purposes.map((purpose, i) => (
              <Line
                key={purpose}
                activeDot={{ r: 4 }}
                dataKey={purpose}
                dot={false}
                isAnimationActive={false}
                stroke={CATEGORICAL[i] ?? INK.muted}
                strokeWidth={2}
                type="linear"
              />
            ))}
          </LineChart>
        </ChartContainer>
      )}
      <p className="text-muted-foreground text-xs">
        Viagens expandidas de moradores de Porto Alegre em dia útil que partem na hora seguinte a
        cada horário, em passos de 15 minutos. Os entrevistados arredondam horários para a hora
        cheia ou a meia hora, e a janela de uma hora evita picos artificiais.
      </p>
    </figure>
  );
}
