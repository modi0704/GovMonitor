import { useMemo, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { OfficeGroup, OfficeRow } from '../api/types';
import { errorMessage, useResource } from '../api/useResource';
import FormError from '../components/FormError';
import Modal from '../components/Modal';
import { useAuth } from '../auth/useAuth';

/** Office groups (P2.4): named sets of offices that are ranked against each other. */
export default function GroupsPage() {
  const { me } = useAuth();
  const groups = useResource<OfficeGroup[]>('groups');
  const offices = useResource<OfficeRow[]>('offices');
  const [editing, setEditing] = useState<OfficeGroup | 'new' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = me?.is_agency_admin ?? false;

  async function remove(g: OfficeGroup) {
    if (!window.confirm(`Delete the group "${g.name}"? The offices themselves are not affected.`))
      return;
    try {
      await api.del(`groups/${g.id}`);
      groups.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <h1>Office groups</h1>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
            New group
          </button>
        )}
      </div>
      <p className="muted">
        A group puts offices from anywhere in the structure side by side, for example “Mainland
        centers”. Rankings are shown for each group.
      </p>
      <FormError message={error ?? groups.error} />
      {groups.loading && <p>Loading…</p>}
      {groups.data && groups.data.length === 0 && (
        <p className="notice">
          No groups yet.{isAdmin ? ' Create one to compare offices that are not siblings.' : ''}
        </p>
      )}
      {groups.data?.map((g) => (
        <div className="card" key={g.id}>
          <div className="page-header">
            <h2>{g.name}</h2>
            {isAdmin && (
              <div className="row">
                <button type="button" className="btn btn-small" onClick={() => setEditing(g)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn btn-small btn-danger"
                  onClick={() => remove(g)}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
          {g.description && <p className="muted">{g.description}</p>}
          {g.members.length === 0 ? (
            <p className="muted small">No offices in this group.</p>
          ) : (
            <ul className="pill-list">
              {g.members.map((m) => (
                <li key={m.id} className={m.is_active ? '' : 'inactive'}>
                  <span className="code">{m.code}</span> {m.name}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      {editing && (
        <GroupDialog
          group={editing === 'new' ? null : editing}
          offices={offices.data ?? []}
          onClose={() => setEditing(null)}
          onDone={groups.reload}
        />
      )}
    </section>
  );
}

function GroupDialog({
  group,
  offices,
  onClose,
  onDone,
}: {
  group: OfficeGroup | null;
  offices: OfficeRow[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [name, setName] = useState(group?.name ?? '');
  const [description, setDescription] = useState(group?.description ?? '');
  const [members, setMembers] = useState<Set<string>>(new Set(group?.members.map((m) => m.id)));
  const [filter, setFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return offices.filter(
      (o) => !f || o.name.toLowerCase().includes(f) || o.code.toLowerCase().includes(f),
    );
  }, [offices, filter]);

  function toggle(id: string) {
    setMembers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const saved = group
        ? await api.patch<OfficeGroup>(`groups/${group.id}`, { name, description })
        : await api.post<OfficeGroup>('groups', { name, description });
      await api.put(`groups/${saved.id}/members`, { office_ids: [...members] });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Modal title={group ? `Edit ${group.name}` : 'New group'} onClose={onClose} wide>
      <form className="stack" onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Description (optional)
          <input value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <fieldset className="checklist">
          <legend>Offices in the group ({members.size} selected)</legend>
          <input
            type="search"
            placeholder="Filter by name or code"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter offices"
          />
          <div className="checklist-items">
            {shown.map((o) => (
              <label key={o.id} className="check" style={{ paddingLeft: `${o.depth * 1.1}rem` }}>
                <input type="checkbox" checked={members.has(o.id)} onChange={() => toggle(o.id)} />
                <span className="code">{o.code}</span> {o.name}
              </label>
            ))}
          </div>
        </fieldset>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={!name.trim()}>
            Save group
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
