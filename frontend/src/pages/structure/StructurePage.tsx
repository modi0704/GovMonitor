import { useMemo, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { Level, OfficeRow } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { useAuth } from '../../auth/useAuth';
import { parseOfficeList, type ParsedRow } from './parseOfficeList';
import { buildTree, subtreeIds, type TreeNode } from './tree';

type Dialog =
  | { kind: 'add'; parent: OfficeRow }
  | { kind: 'rename'; office: OfficeRow }
  | { kind: 'move'; office: OfficeRow }
  | { kind: 'import'; parent: OfficeRow }
  | { kind: 'levels' }
  | null;

export default function StructurePage() {
  const { me } = useAuth();
  const offices = useResource<OfficeRow[]>('offices');
  const levels = useResource<Level[]>('levels');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<Dialog>(null);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = me?.is_agency_admin ?? false;

  const rows = useMemo(() => offices.data ?? [], [offices.data]);
  const tree = useMemo(() => buildTree(rows), [rows]);
  const selected = rows.find((r) => r.id === selectedId) ?? null;
  const childCount = selected ? rows.filter((r) => r.parent_id === selected.id).length : 0;

  function reloadAll() {
    offices.reload();
    levels.reload();
  }

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      reloadAll();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function toggle(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function renderNode(node: TreeNode) {
    const open = !collapsed.has(node.id);
    return (
      <li
        key={node.id}
        role="treeitem"
        aria-expanded={node.children.length ? open : undefined}
        aria-selected={node.id === selectedId}
      >
        <div
          className={`tree-row ${node.id === selectedId ? 'selected' : ''} ${node.is_active ? '' : 'inactive'}`}
        >
          {node.children.length > 0 ? (
            <button
              type="button"
              className="tree-toggle"
              onClick={() => toggle(node.id)}
              aria-label={open ? `Collapse ${node.name}` : `Expand ${node.name}`}
            >
              {open ? '▾' : '▸'}
            </button>
          ) : (
            <span className="tree-toggle" />
          )}
          <button type="button" className="tree-label" onClick={() => setSelectedId(node.id)}>
            <span className="code">{node.code}</span> {node.name}
            <span className="level-tag">{node.level.name}</span>
            {!node.is_active && <span className="chip chip-suspended">inactive</span>}
          </button>
        </div>
        {open && node.children.length > 0 && <ul role="group">{node.children.map(renderNode)}</ul>}
      </li>
    );
  }

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Structure</h1>
        {isAdmin && (
          <button type="button" className="btn" onClick={() => setDialog({ kind: 'levels' })}>
            Level names
          </button>
        )}
      </div>
      <p className="muted">
        Your agency's offices, from the top office down. Select an office to change it.
      </p>
      <FormError message={error ?? offices.error} />
      {offices.loading && <p>Loading…</p>}
      {!offices.loading && rows.length === 0 && (
        <p className="notice">No offices are visible to you yet.</p>
      )}
      <div className="split">
        <ul className="tree" role="tree" aria-label="Offices">
          {tree.map(renderNode)}
        </ul>
        {selected && (
          <aside className="card side-panel" aria-label="Selected office">
            <h2>
              {selected.code} {selected.name}
            </h2>
            <p className="muted">
              {selected.level.name} · {selected.is_active ? 'active' : 'inactive'} · {childCount}{' '}
              office{childCount === 1 ? '' : 's'} beneath
            </p>
            {isAdmin ? (
              <div className="stack">
                <button
                  type="button"
                  className="btn"
                  onClick={() => setDialog({ kind: 'add', parent: selected })}
                  disabled={!selected.is_active}
                >
                  Add an office beneath
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setDialog({ kind: 'import', parent: selected })}
                  disabled={!selected.is_active}
                >
                  Paste a list of offices beneath
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setDialog({ kind: 'rename', office: selected })}
                >
                  Rename or change code
                </button>
                {selected.parent_id && (
                  <>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setDialog({ kind: 'move', office: selected })}
                    >
                      Move to…
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        const verb = selected.is_active ? 'Deactivate' : 'Reactivate';
                        const what = selected.is_active
                          ? 'It and every office beneath it will no longer take part in new plans and reports. Their history is kept.'
                          : 'It will take part in plans and reports again.';
                        if (window.confirm(`${verb} ${selected.name}? ${what}`)) {
                          act(() =>
                            api.patch(`offices/${selected.id}`, { is_active: !selected.is_active }),
                          );
                        }
                      }}
                    >
                      {selected.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                    {childCount === 0 && (
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete ${selected.name}? This cannot be undone. Offices with plans or reports cannot be deleted; deactivate them instead.`,
                            )
                          ) {
                            act(async () => {
                              await api.del(`offices/${selected.id}`);
                              setSelectedId(null);
                            });
                          }
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </>
                )}
              </div>
            ) : (
              <p className="muted small">Only the agency administrator can change the structure.</p>
            )}
          </aside>
        )}
      </div>

      {dialog?.kind === 'add' && (
        <AddOfficeDialog
          parent={dialog.parent}
          onClose={() => setDialog(null)}
          onDone={reloadAll}
        />
      )}
      {dialog?.kind === 'rename' && (
        <RenameDialog office={dialog.office} onClose={() => setDialog(null)} onDone={reloadAll} />
      )}
      {dialog?.kind === 'move' && (
        <MoveDialog
          office={dialog.office}
          rows={rows}
          onClose={() => setDialog(null)}
          onDone={reloadAll}
        />
      )}
      {dialog?.kind === 'import' && (
        <ImportDialog parent={dialog.parent} onClose={() => setDialog(null)} onDone={reloadAll} />
      )}
      {dialog?.kind === 'levels' && (
        <LevelsDialog
          levels={levels.data ?? []}
          onClose={() => setDialog(null)}
          onDone={reloadAll}
        />
      )}
    </section>
  );
}

interface DialogProps {
  onClose: () => void;
  onDone: () => void;
}

function AddOfficeDialog({ parent, onClose, onDone }: DialogProps & { parent: OfficeRow }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post('offices', { parent_id: parent.id, name, code });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Modal title={`New office beneath ${parent.name}`} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Code (short and unique, e.g. PME)
          <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={40} required />
        </label>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={!name || !code}>
            Add office
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

function RenameDialog({ office, onClose, onDone }: DialogProps & { office: OfficeRow }) {
  const [name, setName] = useState(office.name);
  const [code, setCode] = useState(office.code);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.patch(`offices/${office.id}`, { name, code });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Modal title={`Rename ${office.name}`} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Code
          <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={40} />
        </label>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary">
            Save
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

function MoveDialog({
  office,
  rows,
  onClose,
  onDone,
}: DialogProps & { office: OfficeRow; rows: OfficeRow[] }) {
  const blocked = useMemo(() => subtreeIds(rows, office.id), [rows, office.id]);
  const targets = rows.filter(
    (r) => !blocked.has(r.id) && r.id !== office.parent_id && r.is_active,
  );
  const [target, setTarget] = useState(targets[0]?.id ?? '');
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`offices/${office.id}/move`, { parent_id: target });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Modal title={`Move ${office.name}`} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <p className="muted">This also moves every office reporting under it.</p>
        <label>
          New supervising office
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {targets.map((r) => (
              <option key={r.id} value={r.id}>
                {'  '.repeat(r.depth)}
                {r.code} {r.name}
              </option>
            ))}
          </select>
        </label>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={!target}>
            Move
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

interface ImportResult {
  rows: { row: number; code: string; name: string; parent_code: string }[];
  errors: { row: number; message: string }[];
  created: number;
}

function ImportDialog({ parent, onClose, onDone }: DialogProps & { parent: OfficeRow }) {
  const [text, setText] = useState('');
  const [parsed, setParsed] = useState<ParsedRow[] | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function check() {
    setError(null);
    const rows = parseOfficeList(text);
    setParsed(rows);
    try {
      setPreview(
        await api.post<ImportResult>('offices/import', {
          parent_id: parent.id,
          rows,
          dry_run: true,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function save() {
    try {
      const res = await api.post<ImportResult>('offices/import', {
        parent_id: parent.id,
        rows: parsed,
      });
      onDone();
      window.alert(`${res.created} offices added.`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const errorsByRow = new Map<number, string[]>();
  preview?.errors.forEach((e) =>
    errorsByRow.set(e.row, [...(errorsByRow.get(e.row) ?? []), e.message]),
  );

  return (
    <Modal title={`Paste offices beneath ${parent.name}`} onClose={onClose} wide>
      <div className="stack">
        <p className="muted small">
          One office per line: code, then name, separated by a tab (as copied from Excel), “ - ” or
          a comma. Indent a line (tab or two spaces) to put it beneath the line above, or add a
          third column with the parent's code.
        </p>
        <textarea
          rows={10}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setPreview(null);
          }}
          aria-label="Offices to add"
          placeholder="Enter your office codes and names, one office per line."
          className="mono"
        />
        <FormError message={error} />
        {preview && (
          <>
            <table className="table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Beneath</th>
                  <th>Problem</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr key={r.row} className={errorsByRow.has(r.row) ? 'row-error' : ''}>
                    <td>{parsed?.[r.row - 1]?.line ?? r.row}</td>
                    <td>{r.code}</td>
                    <td>{r.name}</td>
                    <td>{r.parent_code}</td>
                    <td>{errorsByRow.get(r.row)?.join('; ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.errors.length > 0 ? (
              <p className="form-error">
                Fix the lines marked above; nothing is saved until every line is valid.
              </p>
            ) : (
              <p className="notice">{preview.rows.length} offices are ready to add.</p>
            )}
          </>
        )}
        <div className="row">
          <button type="button" className="btn" onClick={check} disabled={!text.trim()}>
            Preview
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={save}
            disabled={!preview || preview.errors.length > 0}
          >
            Add offices
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}

function LevelsDialog({ levels, onClose, onDone }: DialogProps & { levels: Level[] }) {
  const [names, setNames] = useState(levels.map((l) => l.name));
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.put('levels', { names });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Modal title="Level names" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <p className="muted small">
          Name the groups of offices from the top down, such as Ministry, Service, and Division.
          Reports use these names.
        </p>
        {names.map((n, i) => (
          <label key={i}>
            Level {i}
            {levels[i] ? ` (${levels[i].office_count} offices)` : ' (new)'}
            <input
              value={n}
              onChange={(e) => setNames(names.map((x, j) => (j === i ? e.target.value : x)))}
            />
          </label>
        ))}
        <button type="button" className="btn btn-link" onClick={() => setNames([...names, ''])}>
          Add another level below
        </button>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary">
            Save
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
