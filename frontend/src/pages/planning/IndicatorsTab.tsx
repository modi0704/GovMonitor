import { useEffect, useMemo, useState } from 'react';
import { newKey } from './gridModel';
import type { PlanDetail } from './PlanEditorPage';

export interface ServerIndicator {
  id: string;
  code: string;
  name: string;
  kind: 'outcome' | 'output';
  unit: string;
  annual_target: string;
  weight: string | null;
  aggregation: 'sum' | 'last';
  sort_order: number;
  targets: string[];
}

interface IndRow {
  key: string;
  id: string | null;
  code: string;
  name: string;
  kind: 'outcome' | 'output';
  unit: string;
  annual_target: string;
  weight: string;
  aggregation: 'sum' | 'last';
  targets: string[];
}

function fromServer(list: ServerIndicator[]): IndRow[] {
  return list.map((i) => ({
    key: i.id,
    id: i.id,
    code: i.code,
    name: i.name,
    kind: i.kind,
    unit: i.unit,
    annual_target: i.annual_target === '0.0000' ? '' : String(Number(i.annual_target)),
    weight: i.weight ?? '',
    aggregation: i.aggregation,
    targets: i.targets.map((t) => (t === '0' ? '' : t)),
  }));
}

const clean = (v: string) => v.replace(/[,\s]/g, '');

/** Indicators of a plan (P5.6): name, unit, kind, annual target, weight, monthly targets. */
export default function IndicatorsTab({
  plan,
  readOnly,
  months,
  onChange,
}: {
  plan: PlanDetail;
  readOnly: boolean;
  months: string[];
  onChange: (payload: Record<string, unknown>, dirty: boolean) => void;
}) {
  const saved = useMemo(() => fromServer(plan.indicators), [plan.indicators]);
  const [rows, setRows] = useState<IndRow[]>(saved);
  // After a save the plan comes back with the new indicators' ids: show those, or the new rows
  // would stay "unsaved" and be sent (and created) again by the next save.
  const [shown, setShown] = useState(saved);
  if (shown !== saved) {
    setShown(saved);
    setRows(saved);
  }

  useEffect(() => {
    const before = new Map(saved.map((r) => [r.key, JSON.stringify(r)]));
    const changed = rows
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => !r.id || before.get(r.key) !== JSON.stringify(r))
      .map(({ r, i }) => ({
        ...(r.id ? { id: r.id } : { client_key: r.key }),
        code: r.code,
        name: r.name,
        kind: r.kind,
        unit: r.unit,
        annual_target: clean(r.annual_target) || '0',
        weight: clean(r.weight) || null,
        aggregation: r.aggregation,
        sort_order: (i + 1) * 10,
        targets: r.targets.map((t) => clean(t) || '0'),
      }));
    const live = new Set(rows.map((r) => r.key));
    const deleted = saved.filter((r) => !live.has(r.key)).map((r) => r.id!);
    onChange(
      { indicators: changed, deleted_indicators: deleted },
      changed.length > 0 || deleted.length > 0,
    );
  }, [rows, saved, onChange]);

  const set = (index: number, patch: Partial<IndRow>) =>
    setRows(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  const issues = plan.issues.filter((i) => i.indicator);

  return (
    <div className="stack">
      <p className="muted small">
        Indicators track results, such as people trained. Their scores compare reported results with
        the yearly target and are kept separate from activity scores.
      </p>
      {issues.length > 0 && (
        <ul className="form-message">
          {issues.map((i, n) => (
            <li key={n}>{i.message}</li>
          ))}
        </ul>
      )}
      <div className="grid-scroll">
        <table className="grid" aria-label="Plan indicators">
          <thead>
            <tr>
              <th>Code</th>
              <th>Indicator</th>
              <th>Kind</th>
              <th>Unit</th>
              <th>Annual target</th>
              <th>Weight</th>
              <th>Counted as</th>
              {months.map((m) => (
                <th key={m}>{m}</th>
              ))}
              {!readOnly && <th aria-label="Remove" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.key} className="act">
                <td>
                  <input
                    aria-label={`Code, indicator ${i + 1}`}
                    value={r.code}
                    readOnly={readOnly}
                    onChange={(e) => set(i, { code: e.target.value })}
                  />
                </td>
                <td className="title-cell">
                  <input
                    aria-label={`Indicator ${i + 1}`}
                    value={r.name}
                    readOnly={readOnly}
                    onChange={(e) => set(i, { name: e.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`Kind, indicator ${i + 1}`}
                    value={r.kind}
                    disabled={readOnly}
                    onChange={(e) => set(i, { kind: e.target.value as IndRow['kind'] })}
                  >
                    <option value="output">Output</option>
                    <option value="outcome">Outcome</option>
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`Unit, indicator ${i + 1}`}
                    value={r.unit}
                    readOnly={readOnly}
                    onChange={(e) => set(i, { unit: e.target.value })}
                  />
                </td>
                <td className="num">
                  <input
                    aria-label={`Annual target, indicator ${i + 1}`}
                    inputMode="decimal"
                    value={r.annual_target}
                    readOnly={readOnly}
                    onChange={(e) => set(i, { annual_target: e.target.value })}
                  />
                </td>
                <td className="num">
                  <input
                    aria-label={`Weight, indicator ${i + 1}`}
                    inputMode="decimal"
                    placeholder="equal"
                    value={r.weight}
                    readOnly={readOnly}
                    onChange={(e) => set(i, { weight: e.target.value })}
                  />
                </td>
                <td>
                  <select
                    aria-label={`Counted as, indicator ${i + 1}`}
                    value={r.aggregation}
                    disabled={readOnly}
                    onChange={(e) =>
                      set(i, { aggregation: e.target.value as IndRow['aggregation'] })
                    }
                  >
                    <option value="sum">Total of the months</option>
                    <option value="last">Latest reported result</option>
                  </select>
                </td>
                {r.targets.map((t, m) => (
                  <td key={m} className="num month">
                    <input
                      aria-label={`${months[m]}, indicator ${i + 1}`}
                      inputMode="decimal"
                      value={t}
                      readOnly={readOnly}
                      onChange={(e) =>
                        set(i, { targets: r.targets.map((x, j) => (j === m ? e.target.value : x)) })
                      }
                    />
                  </td>
                ))}
                {!readOnly && (
                  <td>
                    <button
                      type="button"
                      className="btn btn-small btn-danger"
                      aria-label={`Remove indicator ${i + 1}`}
                      onClick={() => setRows(rows.filter((_, j) => j !== i))}
                    >
                      ✕
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="notice">No indicators yet.</p>}
      {!readOnly && (
        <div>
          <button
            type="button"
            className="btn"
            onClick={() =>
              setRows([
                ...rows,
                {
                  key: newKey(),
                  id: null,
                  code: '',
                  name: '',
                  kind: 'output',
                  unit: '',
                  annual_target: '',
                  weight: '',
                  aggregation: 'sum',
                  targets: Array(12).fill(''),
                },
              ])
            }
          >
            Add indicator
          </button>
        </div>
      )}
    </div>
  );
}
