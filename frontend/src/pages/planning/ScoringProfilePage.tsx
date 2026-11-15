import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, api } from '../../api/client';
import type { FiscalYear, Preset, ScoringProfile } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import HelpTip from '../../components/HelpTip';
import { SCORING_TIPS } from './scoringTips';

type Draft = Omit<ScoringProfile, 'id' | 'fiscal_year_id' | 'version' | 'locked_months'>;

interface Choice {
  value: string;
  label: string;
}

/** Every setting of the scoring profile, explained in plain language (P5.2, P12.6). */
const HELP = {
  weighting: {
    title: 'How activities are weighted',
    text: 'Each activity counts towards its office’s score in proportion to this weight.',
    choices: [
      {
        value: 'cost_share',
        label: 'By cost — an activity costing 60% of the plan counts for 60% (the workbook method)',
      },
      { value: 'equal', label: 'Equally — every activity counts the same' },
      {
        value: 'manual',
        label: 'Set by hand — offices type the weights; they must add up to 100%',
      },
    ] as Choice[],
  },
  cap_at_100: {
    title: 'Ceiling at 100%',
    text: 'When on, doing more than planned counts as 100% for that activity. When off, over-delivery raises the score above 100% (the workbook method).',
  },
  on_time_tolerance: {
    title: 'On-time margin (percentage points)',
    text: 'Results this close to the plan, above or below, are labelled on time. 0 means only an exact match is on time.',
  },
  labels: {
    title: 'Status words',
    text: 'The words shown when an office is ahead of, on, or behind its plan.',
  },
  rollup: {
    title: 'How offices add up to their parent',
    text: 'How a service’s score is built from its divisions’ scores.',
    choices: [
      {
        value: 'budget_weighted',
        label: 'By budget — larger budgets weigh more (the workbook method)',
      },
      { value: 'simple_average', label: 'Simple average — every office weighs the same' },
    ] as Choice[],
  },
  indicator_weighting: {
    title: 'How indicators are weighted within an office',
    choices: [
      { value: 'equal', label: 'Equally' },
      { value: 'manual', label: 'By the weight typed for each indicator' },
    ] as Choice[],
  },
  indicator_rollup: {
    title: 'How indicator scores add up to the parent',
    choices: [
      {
        value: 'all_indicators',
        label: 'Average of every indicator beneath it (the workbook method)',
      },
      { value: 'office_scores', label: 'Average of the offices’ indicator scores' },
    ] as Choice[],
  },
  ranking_metric: {
    title: 'What offices are ranked by',
    choices: [
      { value: 'cumulative_actual', label: 'Accomplishment to date (the workbook method)' },
      { value: 'variance', label: 'Accomplishment minus plan' },
      { value: 'actual_over_plan', label: 'Accomplishment as a share of plan' },
    ] as Choice[],
  },
  cutoff_day: {
    title: 'Monthly cutoff day',
    text: 'Reports for a month are due by this day of the following month.',
  },
  auto_lock: {
    title: 'Lock months automatically at cutoff',
    text: 'When on, each month locks by itself once its cutoff passes. When off, the agency administrator locks months by hand.',
  },
  mov_required: {
    title: 'Require supporting files',
    text: 'When on, every reported accomplishment needs at least one supporting file (means of verification) before the report can be submitted.',
  },
  show_actual_amounts: {
    title: 'Ask for amounts actually spent',
    text: 'Adds an optional “amount spent” column to monthly reports. Where filled in, funds used show real amounts instead of the estimate.',
  },
};

function toDraft(p: ScoringProfile): Draft {
  const { id: _id, fiscal_year_id: _fy, version: _v, locked_months: _l, ...rest } = p;
  return rest;
}

export default function ScoringProfilePage() {
  const { fyId } = useParams();
  const { me } = useAuth();
  const fy = useResource<FiscalYear>(`fiscal-years/${fyId}`);
  const presets = useResource<Preset[]>('scoring-presets');
  const [profile, setProfile] = useState<ScoringProfile | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const isAdmin = me?.is_agency_admin ?? false;
  const profileId = fy.data?.profile_id;

  useEffect(() => {
    if (!profileId) return;
    let active = true;
    api
      .get<ScoringProfile>(`scoring-profiles/${profileId}`)
      .then((p) => {
        if (!active) return;
        setProfile(p);
        setDraft(toDraft(p));
      })
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [profileId]);

  if (!draft || !profile) {
    return (
      <section className="page">
        <FormError message={error ?? fy.error} />
        <p>Loading…</p>
      </section>
    );
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
    setDraft({ ...draft, [key]: value });
  };

  async function save(confirm = false) {
    if (!draft || !profile) return;
    setError(null);
    try {
      const updated = await api.patch<ScoringProfile>(`scoring-profiles/${profile.id}`, {
        ...draft,
        confirm,
      });
      setProfile(updated);
      setDraft(toDraft(updated));
      setSaved(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        if (window.confirm(err.message)) await save(true);
        return;
      }
      setError(errorMessage(err));
    }
  }

  function applyPreset(name: string) {
    const p = presets.data?.find((x) => x.name === name);
    if (!p || !draft) return;
    setSaved(false);
    setDraft({ ...draft, ...(p.settings as Partial<Draft>), preset: name });
  }

  const radio = (
    key: 'weighting' | 'rollup' | 'indicator_weighting' | 'indicator_rollup' | 'ranking_metric',
  ) => (
    <fieldset className="setting" disabled={!isAdmin}>
      <legend>
        {HELP[key].title} <HelpTip label={HELP[key].title}>{SCORING_TIPS[key]}</HelpTip>
      </legend>
      {'text' in HELP[key] && <p className="muted small">{(HELP[key] as { text: string }).text}</p>}
      {HELP[key].choices.map((c) => (
        <label key={c.value} className="check">
          <input
            type="radio"
            name={key}
            checked={draft[key] === c.value}
            onChange={() => set(key, c.value as never)}
          />
          {c.label}
        </label>
      ))}
    </fieldset>
  );

  const toggle = (key: 'cap_at_100' | 'auto_lock' | 'mov_required' | 'show_actual_amounts') => (
    <div className="setting">
      <div className="setting-head">
        <label className="check">
          <input
            type="checkbox"
            checked={draft[key]}
            disabled={!isAdmin}
            onChange={(e) => set(key, e.target.checked)}
          />
          <strong>{HELP[key].title}</strong>
        </label>
        <HelpTip label={HELP[key].title}>{SCORING_TIPS[key]}</HelpTip>
      </div>
      <p className="muted small">{HELP[key].text}</p>
    </div>
  );

  return (
    <section className="page">
      <p className="breadcrumb">
        <Link to="/fiscal-years">Fiscal years</Link> › {fy.data?.label}
      </p>
      <h1>Scoring settings · {fy.data?.label}</h1>
      <p className="muted">
        Version {profile.version}.{' '}
        {profile.locked_months > 0
          ? `${profile.locked_months} locked month(s) keep the results they were locked with; changes apply to open months only.`
          : 'No month is locked yet.'}
      </p>
      {!isAdmin && (
        <p className="notice">Only the agency administrator can change these settings.</p>
      )}
      <div className="card stack">
        <h2>
          Start from a preset <HelpTip label="Presets">{SCORING_TIPS.preset}</HelpTip>
        </h2>
        {presets.data?.map((p) => (
          <label key={p.name} className="check">
            <input
              type="radio"
              name="preset"
              checked={draft.preset === p.name}
              disabled={!isAdmin}
              onChange={() => applyPreset(p.name)}
            />
            <span>
              <strong>{p.name.replaceAll('_', ' ')}</strong> —{' '}
              <span className="muted">{p.description}</span>
            </span>
          </label>
        ))}
        {draft.preset === 'custom' && (
          <p className="muted small">The current settings do not match a preset (custom).</p>
        )}
      </div>
      <div className="card stack">
        <h2>Scores</h2>
        {radio('weighting')}
        {toggle('cap_at_100')}
        <div className="setting">
          <label>
            {HELP.on_time_tolerance.title}
            <input
              type="number"
              min={0}
              max={50}
              step={0.1}
              disabled={!isAdmin}
              value={Math.round(Number(draft.on_time_tolerance) * 100000) / 1000}
              onChange={(e) => set('on_time_tolerance', String(Number(e.target.value) / 100))}
            />
          </label>
          <HelpTip label={HELP.on_time_tolerance.title}>{SCORING_TIPS.on_time_tolerance}</HelpTip>
          <p className="muted small">{HELP.on_time_tolerance.text}</p>
        </div>
        <fieldset className="setting" disabled={!isAdmin}>
          <legend>
            {HELP.labels.title} <HelpTip label={HELP.labels.title}>{SCORING_TIPS.labels}</HelpTip>
          </legend>
          <p className="muted small">{HELP.labels.text}</p>
          <div className="row">
            <label>
              Ahead
              <input
                value={draft.label_ahead}
                onChange={(e) => set('label_ahead', e.target.value)}
              />
            </label>
            <label>
              On time
              <input
                value={draft.label_on_time}
                onChange={(e) => set('label_on_time', e.target.value)}
              />
            </label>
            <label>
              Behind
              <input
                value={draft.label_delayed}
                onChange={(e) => set('label_delayed', e.target.value)}
              />
            </label>
          </div>
        </fieldset>
        {radio('rollup')}
        {radio('indicator_weighting')}
        {radio('indicator_rollup')}
        {radio('ranking_metric')}
      </div>
      <div className="card stack">
        <h2>Monthly reporting</h2>
        <div className="setting">
          <label>
            {HELP.cutoff_day.title}
            <input
              type="number"
              min={1}
              max={28}
              disabled={!isAdmin}
              value={draft.cutoff_day}
              onChange={(e) => set('cutoff_day', Number(e.target.value))}
            />
          </label>
          <HelpTip label={HELP.cutoff_day.title}>{SCORING_TIPS.cutoff_day}</HelpTip>
          <p className="muted small">{HELP.cutoff_day.text}</p>
        </div>
        {toggle('auto_lock')}
        {toggle('mov_required')}
        {toggle('show_actual_amounts')}
      </div>
      <FormError message={error} />
      {saved && (
        <p className="notice" role="status">
          Saved (version {profile.version}).
        </p>
      )}
      {isAdmin && (
        <button type="button" className="btn btn-primary" onClick={() => save()}>
          Save settings
        </button>
      )}
    </section>
  );
}
