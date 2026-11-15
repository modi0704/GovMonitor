import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { PlanSummary } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { dateTime, money } from '../../lib/format';

interface RowInfo {
  lineage_id: string;
  code: string;
  title: string;
}
interface Comparison {
  from_version: number;
  to_version: number;
  added: RowInfo[];
  removed: RowInfo[];
  changed: (RowInfo & { changes: Record<string, { before: unknown; after: unknown }> })[];
}

const FIELD = {
  code: 'Code',
  title: 'Title',
  row_kind: 'Kind',
  annual_target: 'Target',
  total_cost: 'Total cost',
  unit: 'Unit',
  implementing_office_id: 'Implementing office',
  targets: 'Monthly targets',
} as Record<string, string>;

function show(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (field === 'targets' && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, string>);
    return entries.length ? entries.map(([m, v]) => `M${m}: ${v}`).join(', ') : 'none';
  }
  return String(value);
}

/** Versions of an office's plan and what changed between two of them (P5.7). */
export default function PlanVersionsPage() {
  const { planId } = useParams();
  const versions = useResource<PlanSummary[]>(`plans/${planId}/versions`);
  const [pair, setPair] = useState<[string, string] | null>(null);
  const [diff, setDiff] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = versions.data ?? [];
  const first = list[0];

  async function compare(a: string, b: string) {
    setPair([a, b]);
    try {
      setDiff(await api.get<Comparison>(`plans/${a}/compare`, { with: b }));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page">
      <p className="breadcrumb">
        <Link to="/plans">Plans</Link> › {first?.office.code} › {first?.fiscal_year.label} ›{' '}
        <Link to={`/plans/${planId}`}>Plan</Link> › Versions
      </p>
      <h1>
        Versions of the {first?.fiscal_year.label} plan · {first?.office.name}
      </h1>
      <FormError message={error ?? versions.error} />
      <table className="table">
        <thead>
          <tr>
            <th>Version</th>
            <th>Status</th>
            <th>Planned cost</th>
            <th>Submitted</th>
            <th>Approved</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {list.map((v, i) => (
            <tr key={v.id}>
              <td>
                <Link to={`/plans/${v.id}`}>Version {v.version}</Link>
              </td>
              <td>
                <span className={`chip chip-plan-${v.status}`}>{v.status}</span>
              </td>
              <td>{money(v.planned_cost)}</td>
              <td>{v.submitted_at ? `${dateTime(v.submitted_at)} · ${v.submitted_by}` : '—'}</td>
              <td>{v.approved_at ? `${dateTime(v.approved_at)} · ${v.approved_by}` : '—'}</td>
              <td className="actions">
                {i < list.length - 1 && (
                  <button
                    type="button"
                    className="btn btn-small"
                    onClick={() => compare(v.id, list[i + 1]!.id)}
                  >
                    Compare with version {list[i + 1]!.version}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {pair && diff && (
        <div className="card stack" aria-live="polite">
          <h2>
            Version {diff.from_version} → version {diff.to_version}
          </h2>
          {diff.added.length + diff.removed.length + diff.changed.length === 0 && (
            <p>No differences.</p>
          )}
          {diff.added.length > 0 && (
            <>
              <h3>Added ({diff.added.length})</h3>
              <ul>
                {diff.added.map((r) => (
                  <li key={r.lineage_id}>
                    <span className="code">{r.code}</span> {r.title}
                  </li>
                ))}
              </ul>
            </>
          )}
          {diff.removed.length > 0 && (
            <>
              <h3>Removed ({diff.removed.length})</h3>
              <p className="muted small">
                Accomplishments already reported for these rows are kept; they are no longer scored
                for open months.
              </p>
              <ul>
                {diff.removed.map((r) => (
                  <li key={r.lineage_id}>
                    <span className="code">{r.code}</span> {r.title}
                  </li>
                ))}
              </ul>
            </>
          )}
          {diff.changed.length > 0 && (
            <>
              <h3>Changed ({diff.changed.length})</h3>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>What</th>
                    <th>Before</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {diff.changed.flatMap((r) =>
                    Object.entries(r.changes).map(([field, c]) => (
                      <tr key={`${r.lineage_id}-${field}`}>
                        <td>
                          <span className="code">{r.code}</span> {r.title.slice(0, 50)}
                        </td>
                        <td>{FIELD[field] ?? field}</td>
                        <td>{show(field, c.before)}</td>
                        <td>{show(field, c.after)}</td>
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </section>
  );
}
