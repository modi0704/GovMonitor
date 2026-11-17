import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError, api } from '../../api/client';
import type { FiscalYear, Preset, ScoringProfile } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import HelpTip from '../../components/HelpTip';
import { SCORING_TIPS } from './scoringTips';
import { scoringMethodDescription, scoringMethodName } from './scoringMethodText';

type Draft = Omit<ScoringProfile, 'id' | 'fiscal_year_id' | 'version' | 'locked_months'>;

interface Choice {
  value: string;
  label: string;
}

/** Every setting of the scoring profile, explained in plain language (P5.2, P12.6). */
const HELP = {
  weighting: {
    title: 'How much each activity counts',
    text: 'Weight means the share of the office’s score assigned to an activity.',
    choices: [
      {
        value: 'cost_share',
        label: 'By cost - an activity using 60% of the planned cost counts for 60% of the score',
      },
      { value: 'equal', label: 'Equally — every activity counts the same' },
      {
        value: 'manual',
        label: 'Enter each share in the plan - all shares must total 100%',
      },
    ] as Choice[],
  },
  cap_at_100: {
    title: 'Limit scores to 100%',
    text: 'Turn on to stop an activity’s score at 100%. Turn off to count work completed above the annual target.',
  },
  on_time_tolerance: {
    title: 'Allowed gap for on-time status (points)',
    text: 'A gap this small, above or below plan, still counts as on time. Enter 0 to require an exact match. A move from 40% to 45% is 5 percentage points.',
  },
  labels: {
    title: 'Status words',
    text: 'The words shown when an office is ahead of, on, or behind its plan.',
  },
  rollup: {
    title: 'Combine office results',
    text: 'Choose how offices contribute to the result of the office they report to.',
    choices: [
      {
        value: 'budget_weighted',
        label: 'By budget - offices with larger budgets count more',
      },
      { value: 'simple_average', label: 'Equal share - every office counts the same' },
    ] as Choice[],
  },
  indicator_weighting: {
    title: 'How much each indicator counts',
    choices: [
      { value: 'equal', label: 'Equally' },
      { value: 'manual', label: 'Use the share entered for each indicator' },
    ] as Choice[],
  },
  indicator_rollup: {
    title: 'Combine indicator results',
    choices: [
      {
        value: 'all_indicators',
        label: 'Average all indicators from the offices below',
      },
      { value: 'office_scores', label: 'Average of the offices’ indicator scores' },
    ] as Choice[],
  },
  ranking_metric: {
    title: 'Rank offices by',
    choices: [
      { value: 'cumulative_actual', label: 'Work completed to date' },
      { value: 'variance', label: 'Gap from plan' },
      { value: 'actual_over_plan', label: 'Completed work compared with work due' },
    ] as Choice[],
  },
  cutoff_day: {
    title: 'Monthly report deadline day',
    text: 'Reports for a month are due by this day of the following month.',
  },
  auto_lock: {
    title: 'Finalize months after the deadline',
    text: 'Automatically lock the month after its deadline, including incomplete reports. Leave off to review and lock each month yourself.',
  },
  mov_required: {
    title: 'Require supporting files',
    text: 'Require a photo or document for every reported accomplishment before the report can be submitted.',
  },
  show_actual_amounts: {
    title: 'Show actual spending',
    text: 'Add an Amount spent column to monthly reports. Once spending is entered, funds used show those amounts. Complete all spending entries to keep totals accurate.',
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
          ? `${profile.locked_months} finalized month(s) keep their current figures. New settings apply only to months still open.`
          : 'No month is locked yet.'}
      </p>
      {!isAdmin && (
        <p className="notice">Only the agency administrator can change these settings.</p>
      )}
      <div className="card stack">
        <h2>
          Choose a starting method <HelpTip label="Starting methods">{SCORING_TIPS.preset}</HelpTip>
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
              <strong>{scoringMethodName(p.name)}</strong> -{' '}
              <span className="muted">{scoringMethodDescription(p.name)}</span>
            </span>
          </label>
        ))}
        {draft.preset === 'custom' && (
          <p className="muted small">You are using your agency’s own combination of settings.</p>
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
