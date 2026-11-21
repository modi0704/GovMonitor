import { Link } from 'react-router-dom';
import { STEPS, type StepKey } from '../lib/steps';

export interface StepState {
  key: StepKey;
  done: boolean;
}

/** Numbered progress bar of the monitoring routine. ``active`` is the step being shown. */
export default function StepProgress({
  states,
  active,
  compact = false,
  linkTo,
}: {
  states: StepState[];
  active: StepKey;
  compact?: boolean;
  linkTo?: (key: StepKey) => string;
}) {
  const done = states.filter((s) => s.done).length;
  const percent = Math.round((done / STEPS.length) * 100);
  const activeIndex = STEPS.findIndex((s) => s.key === active);
  return (
    <div className={`step-progress${compact ? ' is-compact' : ''}`}>
      <div className="step-progress-summary">
        <strong>
          Step {activeIndex + 1} of {STEPS.length}: {STEPS[activeIndex]?.title}
        </strong>
        <span className="muted">
          {done} of {STEPS.length} steps done
        </span>
      </div>
      <div
        className="step-progress-bar"
        role="progressbar"
        aria-label="Steps done"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <ol className="step-progress-list">
        {STEPS.map((step, i) => {
          const state = states.find((s) => s.key === step.key);
          const cls = [
            'step-dot',
            state?.done ? 'is-done' : '',
            step.key === active ? 'is-active' : '',
          ]
            .filter(Boolean)
            .join(' ');
          const content = (
            <>
              <span className="step-number" aria-hidden="true">
                {state?.done ? '✓' : i + 1}
              </span>
              <span className="step-label">{step.short}</span>
              <span className="sr-only">
                {state?.done ? ' (done)' : ''}
                {step.key === active ? ' (current step)' : ''}
              </span>
            </>
          );
          return (
            <li key={step.key} className={cls}>
              {linkTo ? (
                <Link to={linkTo(step.key)} aria-current={step.key === active ? 'step' : undefined}>
                  {content}
                </Link>
              ) : (
                content
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
