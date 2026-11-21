import { Link, useLocation } from 'react-router-dom';
import { STEPS, stepForPath } from '../lib/steps';

/** On a page that belongs to a step, tells the administrator where they are in the routine and
 * how to get back to the step-by-step guide. */
export default function GuideBar() {
  const { pathname } = useLocation();
  const step = stepForPath(pathname);
  if (!step) return null;
  const index = STEPS.indexOf(step);
  const next = STEPS[index + 1];
  return (
    <nav className="guide-bar" aria-label="Where you are">
      <ol className="guide-bar-dots" aria-hidden="true">
        {STEPS.map((s, i) => (
          <li key={s.key} className={i < index ? 'is-before' : i === index ? 'is-active' : ''} />
        ))}
      </ol>
      <span>
        <strong>
          Step {index + 1} of {STEPS.length}:
        </strong>{' '}
        {step.title}
      </span>
      <span className="guide-bar-links">
        <Link to={`/?step=${step.key}`}>← Back to the steps</Link>
        {next && <Link to={`/?step=${next.key}`}>Next: {next.title} →</Link>}
      </span>
    </nav>
  );
}
