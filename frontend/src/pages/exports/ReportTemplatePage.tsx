import { useState } from 'react';
import { api } from '../../api/client';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';

interface TemplateData {
  kind: 'pptx';
  settings: {
    report_title: string;
    primary_color: string;
    accent_color: string;
    footer_text: string;
  };
  customised: boolean;
  logo_url: string | null;
  updated_at: string | null;
}

type Fields = TemplateData['settings'];

/** Report template for the PowerPoint export (P10.2): title, colours, footer, logo. */
export default function ReportTemplatePage() {
  const { me } = useAuth();
  const template = useResource<TemplateData>(me?.is_agency_admin ? 'export-templates/pptx' : null);
  // Unsaved edits over the saved settings (no copying of server data into state).
  const [edits, setEdits] = useState<Partial<Fields>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [logoVersion, setLogoVersion] = useState(0);
  const { data, reload } = template;
  const fields: Fields | null = data ? { ...data.settings, ...edits } : null;

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <h1>Report template</h1>
        <p className="notice">Only the agency administrator can change the report template.</p>
      </section>
    );
  }

  function set<K extends keyof Fields>(key: K, value: Fields[K]) {
    setEdits((e) => ({ ...e, [key]: value }));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!fields) return;
    setError(null);
    try {
      await api.patch('export-templates/pptx', fields);
      setMessage('Saved. New exports use these settings.');
      setEdits({});
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function uploadLogo(file: File) {
    const form = new FormData();
    form.append('file', file);
    setError(null);
    try {
      await api.post('export-templates/pptx/logo', form);
      setLogoVersion((v) => v + 1);
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function removeLogo() {
    await api
      .del('export-templates/pptx/logo')
      .catch((err: unknown) => setError(errorMessage(err)));
    reload();
  }

  async function reset() {
    if (!window.confirm('Restore the standard title, colours, and footer, and remove the logo?'))
      return;
    await api.del('export-templates/pptx').catch((err: unknown) => setError(errorMessage(err)));
    setEdits({});
    setMessage('Standard design restored.');
    reload();
  }

  const color = (value: string) => `#${value.replace(/^#/, '')}`;

  return (
    <section className="page">
      <h1>Report template</h1>
      <p className="muted">
        Choose the appearance of downloaded PowerPoint reports.
        {data?.customised ? '' : 'You are using the standard design.'}
      </p>
      <FormError message={error ?? template.error} />
      {message && <p className="form-message">{message}</p>}
      {fields && (
        <form className="stack" onSubmit={save}>
          <label>
            Report title
            <input
              value={fields.report_title}
              maxLength={120}
              onChange={(e) => set('report_title', e.target.value)}
            />
          </label>
          <div className="row">
            <label>
              Main colour
              <input
                type="color"
                value={color(fields.primary_color)}
                onChange={(e) => set('primary_color', e.target.value)}
              />
            </label>
            <label>
              Highlight colour
              <input
                type="color"
                value={color(fields.accent_color)}
                onChange={(e) => set('accent_color', e.target.value)}
              />
            </label>
          </div>
          <label>
            Footer text
            <input
              value={fields.footer_text}
              maxLength={200}
              placeholder="e.g. For internal use"
              onChange={(e) => set('footer_text', e.target.value)}
            />
          </label>
          <div
            className="template-preview"
            style={{ background: color(fields.primary_color) }}
            aria-label="Header preview"
          >
            <span>{fields.report_title || 'Report title'}</span>
            <span className="template-chip" style={{ background: color(fields.accent_color) }}>
              FINAL
            </span>
          </div>
          <div className="row">
            <button type="submit" className="btn btn-primary">
              Save
            </button>
            {data?.customised && (
              <button type="button" className="btn" onClick={reset}>
                Use the standard design
              </button>
            )}
          </div>
        </form>
      )}
      {data && (
        <div className="stack">
          <h2>Logo</h2>
          {data.logo_url ? (
            <img
              className="template-logo"
              src={`${data.logo_url}?v=${logoVersion}`}
              alt="Current logo"
            />
          ) : (
            <p className="muted">No logo yet. It appears on the title slide.</p>
          )}
          <div className="row">
            <label className="btn">
              {data.logo_url ? 'Replace logo' : 'Upload logo'}
              <input
                type="file"
                accept="image/png,image/jpeg"
                className="sr-only"
                onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])}
              />
            </label>
            {data.logo_url && (
              <button type="button" className="btn" onClick={removeLogo}>
                Remove logo
              </button>
            )}
          </div>
          <p className="muted small">PNG or JPG, at most 2 MB.</p>
        </div>
      )}
    </section>
  );
}
