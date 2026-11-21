import { useState } from 'react';
import { api } from '../../api/client';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';

interface AlertRule {
  remind_days_before: number[];
  delay_threshold: string;
  email_enabled: boolean;
  email_available: boolean;
}

interface Edits {
  days?: string;
  threshold?: string;
  email?: boolean;
}

/** Alert settings (P11.1): reminder days, delay threshold, email on/off. Agency administrator only. */
export default function AlertSettingsPage() {
  const { me } = useAuth();
  const rule = useResource<AlertRule>(me?.is_agency_admin ? 'alert-rules' : null);
  const [edits, setEdits] = useState<Edits>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <h1>Reminders</h1>
        <p className="notice">Only the agency administrator can change alert settings.</p>
      </section>
    );
  }
  const data = rule.data;
  const days = edits.days ?? data?.remind_days_before.join(', ') ?? '';
  const threshold =
    edits.threshold ?? (data ? String(Math.round(Number(data.delay_threshold) * 10000) / 100) : '');
  const email = edits.email ?? data?.email_enabled ?? false;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.patch('alert-rules', {
        remind_days_before: days,
        delay_threshold: String(Number(threshold) / 100),
        email_enabled: email,
      });
      setEdits({});
      setMessage('Saved.');
      rule.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page">
      <h1>Reminders</h1>
      <p className="muted">
        Each morning, the app reminds offices about report deadlines and highlights missing or
        delayed work. Administrators also receive updates on reports, approvals, and final results.
      </p>
      <FormError message={error ?? rule.error} />
      {message && <p className="form-message">{message}</p>}
      {data && (
        <form className="stack" onSubmit={save}>
          <label>
            Remind offices this many days before the deadline
            <input
              value={days}
              inputMode="numeric"
              placeholder="5, 1"
              onChange={(e) => setEdits((x) => ({ ...x, days: e.target.value }))}
            />
            <span className="muted small">Separate several reminders with commas.</span>
          </label>
          <label>
            Alert when an office is behind plan by more than (percentage points)
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={threshold}
              onChange={(e) => setEdits((x) => ({ ...x, threshold: e.target.value }))}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={email}
              disabled={!data.email_available}
              onChange={(e) => setEdits((x) => ({ ...x, email: e.target.checked }))}
            />
            Also send a daily email summary
          </label>
          {!data.email_available && (
            <p className="muted small">
              Email is not set up for this agency. Alerts appear in the app only.
            </p>
          )}
          <div className="row">
            <button type="submit" className="btn btn-primary">
              Save
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
