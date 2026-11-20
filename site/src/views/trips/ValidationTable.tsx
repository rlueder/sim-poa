import type { ValidationCheck } from '../../data/edom';
import { formatInteger, formatPercent } from '../../data/format';

function formatValue(name: string, value: null | number): string {
  if (value === null) return 'não publicado';
  return name.startsWith('Participação') ? formatPercent(value) : formatInteger(value);
}

export function ValidationTable({ checks }: { checks: ValidationCheck[] }) {
  const passed = checks.filter((c) => c.ok).length;
  return (
    <details className="border-border rounded-lg border p-4">
      <summary className="cursor-pointer font-semibold">
        Conferência com o relatório oficial: {passed} de {checks.length} números reproduzidos
      </summary>
      <p className="text-muted-foreground mt-2 text-sm">
        A expansão feita aqui a partir dos microdados é comparada com os números publicados no
        relatório final da pesquisa (EPTC). A hora pico segue o método do relatório: total de
        viagens que chegam ao destino na janela de uma hora, em passos de 15 minutos.
      </p>
      <table className="mt-3 w-full text-sm tabular-nums">
        <thead>
          <tr className="text-muted-foreground text-left">
            <th scope="col">Indicador</th>
            <th className="text-right" scope="col">
              Calculado
            </th>
            <th className="text-right" scope="col">
              Relatório
            </th>
            <th scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check) => (
            <tr key={check.name}>
              <th className="py-1 text-left font-normal" scope="row">
                {check.name}
              </th>
              <td className="text-right">{formatValue(check.name, check.ours)}</td>
              <td className="text-right">{formatValue(check.name, check.report)}</td>
              <td className="pl-3">
                <span aria-hidden>{check.ok ? '✓ ' : '✗ '}</span>
                {check.ok ? 'confere' : 'não confere'}
                <span className="text-muted-foreground"> ({check.note})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
