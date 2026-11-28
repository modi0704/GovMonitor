/** Consistent, decorative line icons. The adjacent link text supplies the accessible name. */
export default function NavIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Steps: 'M4 6h2 M4 12h2 M4 18h2 M9 6h11 M9 12h11 M9 18h11',
    Dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    Rankings: 'M4 20V12h4v8 M10 20V4h4v16 M16 20V8h4v12',
    'Monthly report': 'M6 3h12v18H6z M9 7h6 M9 11h6 M9 15h3',
    Plans: 'M4 5h6l2 2h8v13H4z M8 12h8 M8 16h5',
    'Fiscal years': 'M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4 M8 14h2 M14 14h2',
    Structure: 'M9 3h6v5H9z M4 16h6v5H4z M14 16h6v5h-6z M12 8v4 M7 16v-4h10v4',
    'My exports': 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
    'User guide': 'M12 5v16 M12 5C8 2 4 3 2 4v15c4-2 7-1 10 2 M12 5c4-3 8-2 10-1v15c-4-2-7-1-10 2',
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={paths[name] ?? paths.Dashboard} />
    </svg>
  );
}
