import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
} from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError, api } from '../../api/client';
import { errorMessage, useResource } from '../../api/useResource';
import Chart from '../../components/Chart';
import { CHART_COLORS } from '../../components/chartTheme';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import { monthName, percent } from '../../lib/format';
import {
  GRID_COLUMNS,
  KINDS,
  KIND_LABEL,
  buildSave,
  depths,
  editable,
  emptyRow,
  fromServer,
  getCell,
  isNumberColumn,
  moveRow,
  pasteBlock,
  rowTotal,
  setCell,
  shiftKind,
  type Column,
  type GridRow,
  type Measure,
  type RowKind,
  type ServerRow,
} from './gridModel';
import IndicatorsTab, { type ServerIndicator } from './IndicatorsTab';
import { useUnsavedChanges } from '../../lib/unsaved';

export interface Issue {
  row: string | null;
  indicator: string | null;
  field: string;
  code: string;
  message: string;
  severity: 'warning' | 'error';
}

export interface PlanDetail {
  id: string;
  office: { id: string; code: string; name: string };
  fiscal_year: { id: string; label: string };
  version: number;
  status: 'draft' | 'submitted' | 'approved' | 'superseded';
  approved_budget: string | null;
  planned_cost: string;
  can_edit: boolean;
  office_editable: boolean;
  weighting: 'cost_share' | 'equal' | 'manual';
  notes: string;
  periods: { month_index: number; start_date: string; status: string }[];
  rows: ServerRow[];
  indicators: ServerIndicator[];
  issues: Issue[];
}

interface Preview {
  weights: Record<string, string>;
  cum_plan: string[];
  funds_total: string;
}

interface DirectoryOffice {
  id: string;
  code: string;
  name: string;
  depth: number;
}

const COLUMN_LABEL: Record<string, string> = {
  code: 'Code',
  title: 'Title',
  unit: 'Unit',
  annual_target: 'Target',
  unit_cost: 'Unit cost',
  total_cost: 'Total cost',
  manual_weight: 'Weight',
};

const STATUS_TEXT = {
  draft: 'Draft — being prepared',
  submitted: 'Submitted — waiting for approval',
  approved: 'Approved — the baseline for scoring',
  superseded: 'Superseded — replaced by a later version',
};

export default function PlanEditorPage() {
  const { planId } = useParams();
  const { me } = useAuth();
  const navigate = useNavigate();
  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [rows, setRows] = useState<GridRow[]>([]);
  const [saved, setSaved] = useState<GridRow[]>([]);
  const [history, setHistory] = useState<GridRow[][]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [tab, setTab] = useState<'activities' | 'indicators'>('activities');
  const [indicatorsDirty, setIndicatorsDirty] = useState(false);
  const [indicatorPayload, setIndicatorPayload] = useState<Record<string, unknown>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newKind, setNewKind] = useState<RowKind>('activity');
  const offices = useResource<DirectoryOffice[]>('offices/directory');
  const gridRef = useRef<HTMLTableElement>(null);

  const load = useCallback((data: PlanDetail) => {
    setPlan(data);
    const grid = fromServer(data.rows);
    setRows(grid);
    setSaved(grid);
    setHistory([]);
    setIndicatorsDirty(false);
  }, []);

  useEffect(() => {
    let active = true;
    api
      .get<PlanDetail>(`plans/${planId}`)
      .then((d) => active && load(d))
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [planId, load]);

  // Stable callback: IndicatorsTab reports changes from an effect, so a new function on every
  // render would loop forever.
  const onIndicatorsChange = useCallback((p: Record<string, unknown>, isDirty: boolean) => {
    setIndicatorPayload(p);
    setIndicatorsDirty(isDirty);
  }, []);

  const readOnly = !plan?.can_edit;
  const payload = useMemo(() => buildSave(rows, saved), [rows, saved]);
  const dirty = payload.rows.length > 0 || payload.deleted_rows.length > 0 || indicatorsDirty;

  // Unsaved-changes guard (P12.4).
  useUnsavedChanges('plan-editor', dirty);

  // Live weights and planned curve from the engine (results/preview), debounced.
  useEffect(() => {
    if (!plan) return;
    const activities = rows
      .filter((r) => r.row_kind === 'activity')
      .map((r) => ({
        key: r.key,
        measure_type: r.measure_type,
        annual_target: r.annual_target,
        total_cost: r.total_cost,
        manual_weight: r.manual_weight,
        targets: r.targets,
      }));
    const handle = window.setTimeout(() => {
      api
        .post<Preview>('results/preview', { fiscal_year_id: plan.fiscal_year.id, activities })
        .then(setPreview)
        .catch(() => undefined);
    }, 500);
    return () => window.clearTimeout(handle);
  }, [rows, plan]);

  const update = useCallback(
    (next: GridRow[]) => {
      setHistory((h) => [...h.slice(-99), rows]);
      setRows(next);
    },
    [rows],
  );

  function undo() {
    setHistory((h) => {
      if (!h.length) return h;
      setRows(h[h.length - 1]!);
      return h.slice(0, -1);
    });
  }

  const depth = useMemo(() => depths(rows), [rows]);
  const issuesByRow = useMemo(() => {
    const map = new Map<string, Issue[]>();
    plan?.issues.forEach((i) => i.row && map.set(i.row, [...(map.get(i.row) ?? []), i]));
    return map;
  }, [plan]);

  async function save(): Promise<PlanDetail | null> {
    if (!plan) return null;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ plan: PlanDetail }>(`plans/${plan.id}/save`, {
        ...payload,
        ...indicatorPayload,
      });
      load(res.plan);
      return res.plan;
    } catch (err) {
      setError(errorMessage(err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function action(path: string, confirmText: string, body?: unknown) {
    if (!plan || !window.confirm(confirmText)) return;
    setBusy(true);
    setError(null);
    try {
      if (dirty && !(await save())) return;
      const res = await api.post<PlanDetail>(`plans/${plan.id}/${path}`, body);
      if (path === 'revise') navigate(`/plans/${res.id}`);
      else load(res);
    } catch (err) {
      if (err instanceof ApiError && (err.body as { issues?: Issue[] })?.issues) {
        setPlan({ ...plan, issues: (err.body as { issues: Issue[] }).issues });
      }
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function addRow() {
    const at = selected === null ? rows.length : selected + 1;
    const next = [...rows];
    const row = emptyRow(newKind);
    if (newKind === 'activity') row.implementing_office_id = plan?.office.id ?? null;
    next.splice(at, 0, row);
    update(next);
    setSelected(at);
  }

  function focusCell(r: number, c: number) {
    const el = gridRef.current?.querySelector<HTMLInputElement>(`[data-r="${r}"][data-c="${c}"]`);
    el?.focus();
    el?.select?.();
  }

  function onCellKey(e: KeyboardEvent<HTMLInputElement>, r: number, c: number) {
    const input = e.currentTarget;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      undo();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      save();
    } else if (e.key === 'ArrowDown' || e.key === 'Enter') {
      e.preventDefault();
      focusCell(r + 1, c);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusCell(r - 1, c);
    } else if (e.key === 'ArrowRight' && input.selectionStart === input.value.length) {
      e.preventDefault();
      focusCell(r, c + 1);
    } else if (e.key === 'ArrowLeft' && input.selectionStart === 0) {
      e.preventDefault();
      focusCell(r, c - 1);
    }
  }

  function onCellPaste(e: ClipboardEvent<HTMLInputElement>, r: number, col: Column) {
    const text = e.clipboardData.getData('text/plain');
    if (!text.includes('\t') && !text.includes('\n')) return; // single value: normal paste
    e.preventDefault();
    update(pasteBlock(rows, r, col, text));
  }

  if (!plan) {
    return (
      <section className="page">
        <FormError message={error} />
        <p>Loading…</p>
      </section>
    );
  }

  const months = plan.periods.map((p) => monthName(p.start_date, true));
  const activityRows = rows.filter((r) => r.row_kind === 'activity');
  const weightTable = activityRows.map((r) => [
    r.code || r.title.slice(0, 30),
    percent(preview?.weights[r.key] ?? null),
  ]);
  const sel = selected !== null ? rows[selected] : undefined;
  const isAdmin = me?.is_agency_admin ?? false;
  const errors = plan.issues.filter((i) => i.severity === 'error');

  return (
    <section className="page page-full">
      <p className="breadcrumb">
        <Link to="/plans">Plans</Link> › {plan.office.code} › {plan.fiscal_year.label}
      </p>
      <div className="page-header">
        <h1>
          {plan.office.name} · {plan.fiscal_year.label} plan, version {plan.version}
        </h1>
        <span className={`chip chip-plan-${plan.status}`}>{STATUS_TEXT[plan.status]}</span>
      </div>

      <div className="toolbar" role="toolbar" aria-label="Plan actions">
        {!readOnly && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={save}
              disabled={busy || !dirty}
            >
              {dirty ? 'Save' : 'Saved'}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() =>
                action(
                  'submit',
                  'Submit this plan for approval? It cannot be edited while it waits.',
                )
              }
            >
              Submit for approval
            </button>
          </>
        )}
        {isAdmin && plan.status === 'submitted' && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() =>
                action(
                  'approve',
                  'Approve this plan? It becomes the baseline that monthly reports are scored against.',
                )
              }
            >
              Approve
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => {
                const note = window.prompt('Why is it returned? The office sees this note.') ?? '';
                if (note)
                  action('return', 'Return the plan to the office for correction?', { note });
              }}
            >
              Return for correction
            </button>
          </>
        )}
        {plan.status === 'approved' && plan.office_editable && (
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() =>
              action(
                'revise',
                'Start a revision? A new draft version is created; the approved version stays in force until the revision is approved.',
              )
            }
          >
            Revise plan
          </button>
        )}
        <Link className="btn" to={`/plans/${plan.id}/versions`}>
          Versions
        </Link>
        <span className="toolbar-spacer" />
        <span className="muted small">
          Planned cost{' '}
          {Number(plan.planned_cost).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
          {plan.approved_budget &&
            ` · approved budget ${Number(plan.approved_budget).toLocaleString('en-PH', { minimumFractionDigits: 2 })}`}
        </span>
      </div>

      <FormError message={error} />
      {errors.length > 0 && (
        <details className="issues" open>
          <summary>{errors.length} problem(s) must be fixed before submitting</summary>
          <ul>
            {errors.map((i, n) => (
              <li key={n}>{i.message}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'activities'}
          onClick={() => setTab('activities')}
        >
          Activities ({activityRows.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'indicators'}
          onClick={() => setTab('indicators')}
        >
          Indicators ({plan.indicators.length})
        </button>
      </div>

      {tab === 'indicators' ? (
        <IndicatorsTab
          plan={plan}
          readOnly={readOnly}
          months={months}
          onChange={onIndicatorsChange}
        />
      ) : (
        <div className="editor-layout">
          <div className="editor-main">
            {!readOnly && (
              <div className="toolbar small" role="toolbar" aria-label="Rows">
                <label className="inline">
                  New row
                  <select value={newKind} onChange={(e) => setNewKind(e.target.value as RowKind)}>
                    {KINDS.map((k) => (
                      <option key={k} value={k}>
                        {KIND_LABEL[k]}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" className="btn btn-small" onClick={addRow}>
                  Add {selected !== null ? 'below selected' : 'at end'}
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={!sel || sel.row_kind === 'activity'}
                  onClick={() =>
                    selected !== null &&
                    update(rows.map((r, i) => (i === selected ? shiftKind(r, -1) : r)))
                  }
                >
                  Outdent
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={!sel || sel.row_kind === 'activity'}
                  onClick={() =>
                    selected !== null &&
                    update(rows.map((r, i) => (i === selected ? shiftKind(r, 1) : r)))
                  }
                >
                  Indent
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={selected === null || selected === 0}
                  onClick={() => {
                    if (selected !== null) {
                      update(moveRow(rows, selected, -1));
                      setSelected(selected - 1);
                    }
                  }}
                >
                  Move up
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={selected === null || selected >= rows.length - 1}
                  onClick={() => {
                    if (selected !== null) {
                      update(moveRow(rows, selected, 1));
                      setSelected(selected + 1);
                    }
                  }}
                >
                  Move down
                </button>
                <button
                  type="button"
                  className="btn btn-small btn-danger"
                  disabled={selected === null}
                  onClick={() => {
                    if (selected !== null) {
                      update(rows.filter((_, i) => i !== selected));
                      setSelected(null);
                    }
                  }}
                >
                  Delete row
                </button>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={!history.length}
                  onClick={undo}
                >
                  Undo
                </button>
                <span className="muted small">
                  Tip: paste a block straight from Excel; Enter and arrow keys move between cells;
                  Ctrl+Z undoes.
                </span>
              </div>
            )}
            {rows.length === 0 ? (
              <p className="notice">
                This plan is empty.{' '}
                {readOnly
                  ? ''
                  : 'Add an outcome or output, then the activities beneath it — or paste them from Excel.'}
              </p>
            ) : (
              <div className="grid-scroll">
                <table className="grid" ref={gridRef} aria-label="Plan activities">
                  <thead>
                    <tr>
                      <th className="sticky-col">Kind</th>
                      {GRID_COLUMNS.slice(0, 6).map((c) => (
                        <th key={c}>{COLUMN_LABEL[c]}</th>
                      ))}
                      <th title="Computed by the scoring rules; typed by hand only under manual weighting">
                        Weight
                      </th>
                      <th>Measure</th>
                      <th>Implementing office</th>
                      {months.map((m) => (
                        <th key={m}>{m}</th>
                      ))}
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, r) => {
                      const isAct = row.row_kind === 'activity';
                      const rowIssues = row.id ? (issuesByRow.get(row.id) ?? []) : [];
                      const total = rowTotal(row);
                      const target = Number(row.annual_target || 0);
                      const sumOff =
                        isAct &&
                        row.measure_type !== 'recurring' &&
                        target > 0 &&
                        Math.abs(total - target) > 0.0001;
                      return (
                        <tr
                          key={row.key}
                          className={`${isAct ? 'act' : 'outline'} ${selected === r ? 'selected' : ''} ${rowIssues.some((i) => i.severity === 'error') ? 'has-error' : ''}`}
                          onClick={() => setSelected(r)}
                        >
                          <td
                            className="sticky-col kind"
                            style={{ paddingLeft: `${0.4 + (depth.get(row.key) ?? 0) * 0.9}rem` }}
                          >
                            {KIND_LABEL[row.row_kind]}
                            {(rowIssues.length > 0 || sumOff) && (
                              <span
                                className="issue-dot"
                                title={[
                                  ...rowIssues.map((i) => i.message),
                                  sumOff ? `Months add up to ${total}, target is ${target}.` : '',
                                ]
                                  .filter(Boolean)
                                  .join('\n')}
                                aria-label="This row has a problem"
                              >
                                !
                              </span>
                            )}
                          </td>
                          {GRID_COLUMNS.slice(0, 6).map((col, c) => (
                            <td
                              key={col}
                              className={
                                col === 'title' ? 'title-cell' : isNumberColumn(col) ? 'num' : ''
                              }
                            >
                              {editable(row, col) ? (
                                <input
                                  data-r={r}
                                  data-c={c}
                                  aria-label={`${COLUMN_LABEL[col]}, row ${r + 1}`}
                                  value={getCell(row, col)}
                                  readOnly={readOnly}
                                  inputMode={isNumberColumn(col) ? 'decimal' : undefined}
                                  onChange={(e) =>
                                    update(
                                      rows.map((x, i) =>
                                        i === r ? setCell(x, col, e.target.value) : x,
                                      ),
                                    )
                                  }
                                  onKeyDown={(e) => onCellKey(e, r, c)}
                                  onPaste={(e) => onCellPaste(e, r, col)}
                                  onFocus={() => setSelected(r)}
                                />
                              ) : null}
                            </td>
                          ))}
                          <td className="num">
                            {isAct &&
                              (plan.weighting === 'manual' ? (
                                <input
                                  data-r={r}
                                  data-c={6}
                                  aria-label={`Weight, row ${r + 1}`}
                                  value={row.manual_weight}
                                  readOnly={readOnly}
                                  onChange={(e) =>
                                    update(
                                      rows.map((x, i) =>
                                        i === r ? setCell(x, 'manual_weight', e.target.value) : x,
                                      ),
                                    )
                                  }
                                  onKeyDown={(e) => onCellKey(e, r, 6)}
                                />
                              ) : (
                                <span className="computed">
                                  {percent(preview?.weights[row.key] ?? null)}
                                </span>
                              ))}
                          </td>
                          <td>
                            {isAct && (
                              <select
                                aria-label={`Measure, row ${r + 1}`}
                                value={row.measure_type ?? 'quantity'}
                                disabled={readOnly}
                                onChange={(e) =>
                                  update(
                                    rows.map((x, i) =>
                                      i === r
                                        ? { ...x, measure_type: e.target.value as Measure }
                                        : x,
                                    ),
                                  )
                                }
                              >
                                <option value="quantity">Quantity</option>
                                <option value="money">Money</option>
                                <option value="recurring">Recurring</option>
                              </select>
                            )}
                          </td>
                          <td>
                            {isAct && (
                              <select
                                aria-label={`Implementing office, row ${r + 1}`}
                                value={row.implementing_office_id ?? plan.office.id}
                                disabled={readOnly}
                                onChange={(e) =>
                                  update(
                                    rows.map((x, i) =>
                                      i === r
                                        ? { ...x, implementing_office_id: e.target.value }
                                        : x,
                                    ),
                                  )
                                }
                              >
                                {(
                                  offices.data ?? [
                                    {
                                      id: plan.office.id,
                                      code: plan.office.code,
                                      name: plan.office.name,
                                      depth: 0,
                                    },
                                  ]
                                ).map((o) => (
                                  <option key={o.id} value={o.id}>
                                    {o.code}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                          {Array.from({ length: 12 }, (_, m) => {
                            const col = `m${m + 1}` as Column;
                            const c = 7 + m;
                            return (
                              <td key={col} className="num month">
                                {isAct && (
                                  <input
                                    data-r={r}
                                    data-c={c}
                                    aria-label={`${months[m]}, row ${r + 1}`}
                                    value={getCell(row, col)}
                                    readOnly={readOnly}
                                    inputMode="decimal"
                                    onChange={(e) =>
                                      update(
                                        rows.map((x, i) =>
                                          i === r ? setCell(x, col, e.target.value) : x,
                                        ),
                                      )
                                    }
                                    onKeyDown={(e) => onCellKey(e, r, c)}
                                    onPaste={(e) => onCellPaste(e, r, col)}
                                    onFocus={() => setSelected(r)}
                                  />
                                )}
                              </td>
                            );
                          })}
                          <td className={`num total ${sumOff ? 'off' : ''}`}>
                            {isAct ? total.toLocaleString('en-PH') : ''}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <aside className="editor-side">
            <Chart
              label="Planned progress (cumulative)"
              height={200}
              option={{
                grid: { left: 40, right: 10, top: 10, bottom: 25 },
                xAxis: { type: 'category', data: months },
                yAxis: {
                  type: 'value',
                  max: 1,
                  axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
                },
                tooltip: { trigger: 'axis', valueFormatter: (v: number) => percent(v) },
                series: [
                  {
                    type: 'line',
                    name: 'Planned',
                    data: (preview?.cum_plan ?? []).map(Number),
                    color: CHART_COLORS.actual,
                    symbol: 'circle',
                  },
                ],
              }}
              table={{
                caption: 'Planned cumulative progress by month',
                headers: ['Month', 'Planned'],
                rows: months.map((m, i) => [m, percent(preview?.cum_plan[i] ?? null)]),
              }}
            />
            <Chart
              label="Weight of each activity"
              height={Math.max(160, activityRows.length * 18 + 40)}
              option={{
                grid: { left: 70, right: 15, top: 5, bottom: 20 },
                xAxis: {
                  type: 'value',
                  axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
                },
                yAxis: {
                  type: 'category',
                  inverse: true,
                  data: activityRows.map((r) => r.code || r.title.slice(0, 12)),
                },
                tooltip: { valueFormatter: (v: number) => percent(v) },
                series: [
                  {
                    type: 'bar',
                    data: activityRows.map((r) => Number(preview?.weights[r.key] ?? 0)),
                    color: CHART_COLORS.actual,
                  },
                ],
              }}
              table={{
                caption: 'Weight of each activity',
                headers: ['Activity', 'Weight'],
                rows: weightTable,
              }}
            />
          </aside>
        </div>
      )}
    </section>
  );
}
