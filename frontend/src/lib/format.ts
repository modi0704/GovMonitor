/** Shared number and date formatting (P8.7 rules: two decimals with %, pesos with separators). */

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

export function monthName(isoDate: string, short = false): string {
  const m = Number(isoDate.slice(5, 7)) - 1;
  return short ? MONTHS[m]! : MONTH_NAMES[m]!;
}

export function monthYear(isoDate: string): string {
  return `${monthName(isoDate)} ${isoDate.slice(0, 4)}`;
}

export function percent(ratio: string | number | null | undefined, digits = 2): string {
  if (ratio === null || ratio === undefined || ratio === '') return '—';
  return `${(Number(ratio) * 100).toFixed(digits)}%`;
}

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  return `₱${Number(value).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function num(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '';
  const n = Number(value);
  return Number.isInteger(n)
    ? n.toLocaleString('en-PH')
    : n.toLocaleString('en-PH', { maximumFractionDigits: digits });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' });
}
