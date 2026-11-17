/** Consistent, decorative line icons. The adjacent link text supplies the accessible name. */
export default function NavIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    Rankings: 'M4 20V12h4v8 M10 20V4h4v16 M16 20V8h4v12',
    'Monthly report': 'M6 3h12v18H6z M9 7h6 M9 11h6 M9 15h3',
    Submissions: 'M4 4h16v16H4z M8 12l3 3 5-6',
    Plans: 'M4 5h6l2 2h8v13H4z M8 12h8 M8 16h5',
    Approvals: 'M12 3l8 4v6c0 4-8 8-8 8s-8-4-8-8V7z M8 12l3 3 5-6',
    'Fiscal years': 'M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4 M8 14h2 M14 14h2',
    Structure: 'M9 3h6v5H9z M4 16h6v5H4z M14 16h6v5h-6z M12 8v4 M7 16v-4h10v4',
    Groups:
      'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.9 M16 3.1a4 4 0 0 1 0 7.8',
    Users: 'M20 21v-2a7 7 0 0 0-14 0v2 M13 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
    Funds: 'M3 6h16v14H3z M3 6V4h13v2 M15 11h6v5h-6z M18 13.5h.01',
    'My exports': 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
    Alerts: 'M6 16V10a6 6 0 0 1 12 0v6l2 2H4z M10 21h4',
    'Report template': 'M4 3h16v18H4z M4 8h16 M9 8v13',
    'Audit log': 'M4 6v5h5 M4 11a8 8 0 1 1 1 7 M12 7v5l3 2',
    Help: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 17h.01',
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
