import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/useAuth';
import { GUIDES, type Guide } from './guides';

/** In-app help (P12.6): a one-page guide per role, the reader's own role first. */
export default function HelpPage() {
  const { me } = useAuth();
  const own: Guide['key'] = me?.is_agency_admin
    ? 'agency_admin'
    : me?.roles.some((r) => r.level === 'admin')
      ? 'office_admin'
      : 'viewer';
  const [chosen, setChosen] = useState<Guide['key'] | null>(null);
  const key = chosen ?? own;
  const guide = GUIDES.find((g) => g.key === key)!;
  return (
    <section className="page">
      <h1>Help</h1>
      <p>
        <Link className="btn btn-primary" to="/user-guide">
          Open full user guide
        </Link>
      </p>
      <div className="tabs" role="tablist" aria-label="Guides">
        {GUIDES.map((g) => (
          <button
            key={g.key}
            type="button"
            role="tab"
            aria-selected={g.key === key}
            onClick={() => setChosen(g.key)}
          >
            {g.title}
            {g.key === own ? ' (you)' : ''}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={guide.title} className="help-guide">
        <p className="muted">{guide.who}</p>
        {guide.sections.map((s) => (
          <div key={s.heading} className="card">
            <h2>{s.heading}</h2>
            <ol>
              {s.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  );
}
