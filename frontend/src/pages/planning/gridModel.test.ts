import {
  buildSave,
  depths,
  emptyRow,
  fromServer,
  moveRow,
  parents,
  pasteBlock,
  rowTotal,
  shiftKind,
  type GridRow,
} from './gridModel';

function row(kind: GridRow['row_kind'], code: string, id: string | null = null): GridRow {
  return { ...emptyRow(kind), key: id ?? code, id, code, title: code };
}

describe('outline structure', () => {
  const rows = [
    row('outcome', 'OC'),
    row('output', 'O1'),
    row('activity', 'A1'),
    row('activity', 'A2'),
    row('program', 'P'),
    row('activity', 'A3'),
    row('output', 'O2'),
    row('activity', 'A4'),
  ];

  it('derives parents from order and kind', () => {
    const p = parents(rows);
    expect([...p.entries()]).toEqual([
      ['OC', null],
      ['O1', 'OC'],
      ['A1', 'O1'],
      ['A2', 'O1'],
      ['P', 'O1'],
      ['A3', 'P'],
      ['O2', 'OC'],
      ['A4', 'O2'],
    ]);
    expect(depths(rows).get('A3')).toBe(3);
  });

  it('indents outline rows by kind and never activities', () => {
    expect(shiftKind(row('output', 'x'), 1).row_kind).toBe('output_indicator');
    expect(shiftKind(row('outcome', 'x'), -1).row_kind).toBe('outcome');
    expect(shiftKind(row('project', 'x'), 1).row_kind).toBe('project');
    expect(shiftKind(row('activity', 'x'), -1).row_kind).toBe('activity');
  });

  it('moves rows', () => {
    expect(
      moveRow(rows, 2, 1)
        .map((r) => r.code)
        .slice(1, 4),
    ).toEqual(['O1', 'A2', 'A1']);
    expect(moveRow(rows, 0, -1)).toBe(rows);
  });
});

describe('paste from Excel', () => {
  it('fills a block across columns and rows, cleaning numbers and skipping outline cells', () => {
    const rows = [row('activity', 'A'), row('output', 'O'), row('activity', 'B')];
    const pasted = pasteBlock(
      rows,
      0,
      'annual_target',
      '1,200\t50\t60,000\n9\t9\t9\n3\t\t(5)\nignored',
    );
    expect([pasted[0]!.annual_target, pasted[0]!.unit_cost, pasted[0]!.total_cost]).toEqual([
      '1200',
      '50',
      '60000',
    ]);
    expect(pasted[1]!.annual_target).toBe(''); // outline row: not editable
    expect([pasted[2]!.annual_target, pasted[2]!.unit_cost, pasted[2]!.total_cost]).toEqual([
      '3',
      '',
      '-5',
    ]);
  });

  it('pastes a year of months', () => {
    const [r] = pasteBlock(
      [row('activity', 'A')],
      0,
      'm1',
      '1\t2\t3\t4\t5\t6\t7\t8\t9\t10\t11\t12\t13',
    );
    expect(r!.targets).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']);
    expect(rowTotal(r!)).toBe(78);
  });
});

describe('save payload', () => {
  it('sends only changed and new rows, with parent references and deletions', () => {
    const saved = fromServer([
      {
        id: 'o',
        parent: null,
        row_kind: 'output',
        code: 'O',
        title: 'O',
        sort_order: 10,
        measure_type: null,
        unit: '',
        annual_target: null,
        unit_cost: null,
        total_cost: null,
        manual_weight: null,
        implementing_office_id: null,
        targets: Array(12).fill('0'),
      },
      {
        id: 'a',
        parent: 'o',
        row_kind: 'activity',
        code: 'A',
        title: 'A',
        sort_order: 20,
        measure_type: 'quantity',
        unit: '',
        annual_target: '4',
        unit_cost: null,
        total_cost: '10',
        manual_weight: null,
        implementing_office_id: 'x',
        targets: ['4', ...Array(11).fill('0')],
      },
      {
        id: 'b',
        parent: 'o',
        row_kind: 'activity',
        code: 'B',
        title: 'B',
        sort_order: 30,
        measure_type: 'quantity',
        unit: '',
        annual_target: '1',
        unit_cost: null,
        total_cost: '1',
        manual_weight: null,
        implementing_office_id: 'x',
        targets: ['1', ...Array(11).fill('0')],
      },
    ]);
    expect(buildSave(saved, saved)).toEqual({ rows: [], deleted_rows: [] });
    const fresh = {
      ...emptyRow('activity'),
      key: 'new1',
      code: 'C',
      title: 'C',
      annual_target: '2',
    };
    const edited = [saved[0]!, { ...saved[1]!, title: 'A!' }, fresh];
    const payload = buildSave(edited, saved);
    expect(payload.deleted_rows).toEqual(['b']);
    expect(payload.rows.map((r) => r.id ?? r.client_key)).toEqual(['a', 'new1']);
    expect(payload.rows[1]).toMatchObject({
      client_key: 'new1',
      parent: 'o',
      annual_target: '2',
      sort_order: 30,
    });
    expect((payload.rows[0]!.targets as string[])[1]).toBe('0');
  });
});
