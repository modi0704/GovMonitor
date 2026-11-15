/**
 * Plan editor state (P5.5). Pure functions, no React: easy to test.
 *
 * Rows are kept in display order. An outline row's kind decides its indentation (outcome is the
 * outermost, project the innermost — the same columns as the Excel layout), and every row's parent
 * is the nearest earlier row of a higher kind. So "indent" changes an outline row's kind, and an
 * activity always hangs under the outline row above it.
 */

export const KINDS = [
  'outcome',
  'outcome_indicator',
  'output',
  'output_indicator',
  'program',
  'project',
  'activity',
] as const;
export type RowKind = (typeof KINDS)[number];
export type Measure = 'quantity' | 'money' | 'recurring';

export const KIND_LABEL: Record<RowKind, string> = {
  outcome: 'Outcome',
  outcome_indicator: 'Outcome indicator',
  output: 'Output',
  output_indicator: 'Output indicator',
  program: 'Program',
  project: 'Project',
  activity: 'Activity',
};

export interface GridRow {
  key: string; // stable client key: the server id for saved rows
  id: string | null; // server id, null until saved
  row_kind: RowKind;
  code: string;
  title: string;
  measure_type: Measure | null;
  unit: string;
  annual_target: string;
  unit_cost: string;
  total_cost: string;
  manual_weight: string;
  implementing_office_id: string | null;
  targets: string[]; // 12 monthly values
}

export interface ServerRow {
  id: string;
  parent: string | null;
  row_kind: RowKind;
  code: string;
  title: string;
  sort_order: number;
  measure_type: Measure | null;
  unit: string;
  annual_target: string | null;
  unit_cost: string | null;
  total_cost: string | null;
  manual_weight: string | null;
  implementing_office_id: string | null;
  targets: string[];
}

/** Editable columns, in grid order. Months are `m1`…`m12`. */
export const TEXT_COLUMNS = ['code', 'title', 'unit'] as const;
export const NUMBER_COLUMNS = [
  'annual_target',
  'unit_cost',
  'total_cost',
  'manual_weight',
] as const;
export type Column = (typeof TEXT_COLUMNS)[number] | (typeof NUMBER_COLUMNS)[number] | `m${number}`;
export const GRID_COLUMNS: Column[] = [
  'code',
  'title',
  'unit',
  'annual_target',
  'unit_cost',
  'total_cost',
  'manual_weight',
  ...Array.from({ length: 12 }, (_, i) => `m${i + 1}` as Column),
];

let counter = 0;
export function newKey(): string {
  counter += 1;
  return `new-${Date.now().toString(36)}-${counter}`;
}

export function rank(kind: RowKind): number {
  return KINDS.indexOf(kind);
}

export function emptyRow(kind: RowKind): GridRow {
  return {
    key: newKey(),
    id: null,
    row_kind: kind,
    code: '',
    title: '',
    measure_type: kind === 'activity' ? 'quantity' : null,
    unit: '',
    annual_target: '',
    unit_cost: '',
    total_cost: '',
    manual_weight: '',
    implementing_office_id: null,
    targets: Array(12).fill(''),
  };
}

/** Server decimals ("10.0000", "60000.00") shown plainly ("10", "60000"). */
const str = (v: string | null | undefined) =>
  v === null || v === undefined || v === '' ? '' : String(Number(v));
const trimZero = (v: string) => (v === '0' ? '' : v);

export function fromServer(rows: ServerRow[]): GridRow[] {
  return [...rows]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((r) => ({
      key: r.id,
      id: r.id,
      row_kind: r.row_kind,
      code: r.code,
      title: r.title,
      measure_type: r.measure_type,
      unit: r.unit,
      annual_target: str(r.annual_target),
      unit_cost: str(r.unit_cost),
      total_cost: str(r.total_cost),
      manual_weight: str(r.manual_weight),
      implementing_office_id: r.implementing_office_id,
      targets: r.targets.map(trimZero),
    }));
}

/** key -> parent key, derived from order and kind. */
export function parents(rows: GridRow[]): Map<string, string | null> {
  const out = new Map<string, string | null>();
  const stack: GridRow[] = [];
  for (const row of rows) {
    while (stack.length && rank(stack[stack.length - 1]!.row_kind) >= rank(row.row_kind))
      stack.pop();
    out.set(row.key, stack.length ? stack[stack.length - 1]!.key : null);
    if (row.row_kind !== 'activity') stack.push(row);
  }
  return out;
}

/** Indentation level of each row (number of outline ancestors). */
export function depths(rows: GridRow[]): Map<string, number> {
  const p = parents(rows);
  const out = new Map<string, number>();
  for (const row of rows) {
    const parent = p.get(row.key);
    out.set(row.key, parent ? (out.get(parent) ?? 0) + 1 : 0);
  }
  return out;
}

export function getCell(row: GridRow, col: Column): string {
  if (col.startsWith('m') && col !== 'manual_weight')
    return row.targets[Number(col.slice(1)) - 1] ?? '';
  return (row as unknown as Record<string, string>)[col] ?? '';
}

export function setCell(row: GridRow, col: Column, value: string): GridRow {
  if (col.startsWith('m') && col !== 'manual_weight') {
    const targets = [...row.targets];
    targets[Number(col.slice(1)) - 1] = value;
    return { ...row, targets };
  }
  return { ...row, [col]: value };
}

export function isNumberColumn(col: Column): boolean {
  return col !== 'code' && col !== 'title' && col !== 'unit';
}

/** Whether a column can be typed into on this row (outline rows have code and title only). */
export function editable(row: GridRow, col: Column): boolean {
  if (row.row_kind !== 'activity') return col === 'code' || col === 'title';
  return true;
}

/** Normalise a pasted or typed number: drop thousands separators and spaces. */
export function cleanNumber(value: string): string {
  return value.replace(/[,\s₱]/g, '').replace(/^\((.*)\)$/, '-$1');
}

/**
 * Paste a block copied from Excel (tab-separated columns, newline-separated rows) starting at
 * (rowIndex, column). Cells that cannot be edited on a row are skipped. Rows past the end are
 * ignored. Returns the new rows.
 */
export function pasteBlock(
  rows: GridRow[],
  rowIndex: number,
  col: Column,
  text: string,
): GridRow[] {
  const lines = text.replace(/\r/g, '').replace(/\n$/, '').split('\n');
  const startCol = GRID_COLUMNS.indexOf(col);
  const out = [...rows];
  lines.forEach((line, i) => {
    const r = rowIndex + i;
    if (r >= out.length) return;
    let row = out[r]!;
    line.split('\t').forEach((raw, j) => {
      const c = GRID_COLUMNS[startCol + j];
      if (!c || !editable(row, c)) return;
      const value = isNumberColumn(c) ? cleanNumber(raw.trim()) : raw.trim();
      row = setCell(row, c, value);
    });
    out[r] = row;
  });
  return out;
}

/** Sum of the twelve monthly values (display only; not a score). */
export function rowTotal(row: GridRow): number {
  return row.targets.reduce((sum, v) => sum + (Number(cleanNumber(v)) || 0), 0);
}

export function moveRow(rows: GridRow[], index: number, delta: number): GridRow[] {
  const to = index + delta;
  if (to < 0 || to >= rows.length) return rows;
  const out = [...rows];
  const [row] = out.splice(index, 1);
  out.splice(to, 0, row!);
  return out;
}

/** Outline rows step one kind inwards (indent, +1) or outwards (outdent, -1). */
export function shiftKind(row: GridRow, delta: number): GridRow {
  if (row.row_kind === 'activity') return row;
  const next = rank(row.row_kind) + delta;
  if (next < 0 || next > KINDS.indexOf('project')) return row;
  return { ...row, row_kind: KINDS[next]! };
}

export interface SavePayload {
  rows: Record<string, unknown>[];
  deleted_rows: string[];
}

function rowSignature(row: GridRow, parent: string | null, order: number): string {
  return JSON.stringify([row, parent, order]);
}

/** Build the bulk-save payload: changed or new rows (with parents and order) and deletions. */
export function buildSave(rows: GridRow[], saved: GridRow[]): SavePayload {
  const p = parents(rows);
  const savedParents = parents(saved);
  const savedIndex = new Map(saved.map((r, i) => [r.key, i]));
  const before = new Map(
    saved.map((r, i) => [r.key, rowSignature(r, savedParents.get(r.key) ?? null, i)]),
  );
  const out: Record<string, unknown>[] = [];
  rows.forEach((row, index) => {
    const parentKey = p.get(row.key) ?? null;
    const sig = rowSignature(row, parentKey, savedIndex.has(row.key) ? index : -1);
    if (row.id && before.get(row.key) === sig) return;
    const parentRow = parentKey ? rows.find((r) => r.key === parentKey) : undefined;
    const isActivity = row.row_kind === 'activity';
    out.push({
      ...(row.id ? { id: row.id } : { client_key: row.key }),
      parent: parentRow ? (parentRow.id ?? parentRow.key) : null,
      row_kind: row.row_kind,
      code: row.code,
      title: row.title,
      sort_order: (index + 1) * 10,
      ...(isActivity
        ? {
            measure_type: row.measure_type,
            unit: row.unit,
            annual_target: cleanNumber(row.annual_target) || null,
            unit_cost: cleanNumber(row.unit_cost) || null,
            total_cost: cleanNumber(row.total_cost) || null,
            manual_weight: cleanNumber(row.manual_weight) || null,
            implementing_office_id: row.implementing_office_id,
            targets: row.targets.map((v) => cleanNumber(v) || '0'),
          }
        : {}),
    });
  });
  const live = new Set(rows.map((r) => r.key));
  const deleted = saved.filter((r) => r.id && !live.has(r.key)).map((r) => r.id!);
  return { rows: out, deleted_rows: deleted };
}
