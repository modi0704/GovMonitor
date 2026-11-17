/** Small, truthful history chart. Missing values break the line; they never become zeroes. */
export default function Sparkline({
  values,
  planned,
  label,
  tone = 'positive',
}: {
  values: (number | null)[];
  planned?: (number | null)[];
  label: string;
  tone?: 'positive' | 'negative' | 'neutral';
}) {
  const all = [...values, ...(planned ?? [])].filter(
    (v): v is number => v !== null && Number.isFinite(v),
  );
  if (!all.length) return null;
  const low = Math.min(0, ...all);
  const high = Math.max(low + 0.01, ...all);
  const x = (i: number) => (values.length <= 1 ? 140 : 4 + (i / (values.length - 1)) * 272);
  const y = (v: number) => 38 - ((v - low) / (high - low)) * 32;
  const path = (points: (number | null)[]) => {
    let connected = false;
    return points
      .map((v, i) => {
        if (v === null || !Number.isFinite(v)) {
          connected = false;
          return '';
        }
        const segment = `${connected ? 'L' : 'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`;
        connected = true;
        return segment;
      })
      .join(' ');
  };
  return (
    <svg
      className={`sparkline sparkline-${tone}`}
      viewBox="0 0 280 44"
      role="img"
      aria-label={label}
    >
      <path className="sparkline-baseline" d="M4 39H276" />
      {planned && <path className="sparkline-plan" d={path(planned)} />}
      <path className="sparkline-actual" d={path(values)} />
      {values.map(
        (v, i) =>
          v !== null &&
          Number.isFinite(v) && (
            <circle key={i} cx={x(i)} cy={y(v)} r={values.length === 1 ? 3 : 1.6} />
          ),
      )}
    </svg>
  );
}
