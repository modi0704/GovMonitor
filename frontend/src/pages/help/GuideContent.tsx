import { Fragment, type ReactNode } from 'react';

function safeLink(href: string) {
  if (/^https?:\/\//i.test(href) || href.startsWith('#')) return href;
  return undefined;
}

/** Render the guide's small Markdown vocabulary as React nodes, never injected HTML. */
function inline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);
  return parts.map((part, i) => {
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*')) return <em key={i}>{part.slice(1, -1)}</em>;
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (link) {
      const href = safeLink(link[2]!);
      return href ? (
        <a key={i} href={href}>
          {link[1]}
        </a>
      ) : (
        <Fragment key={i}>{link[1]}</Fragment>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export default function GuideContent({ markdown }: { markdown: string }) {
  const lines = markdown.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  const tableCells = (line: string) =>
    line
      .trim()
      .replace(/^\||\|$/g, '')
      .split('|');
  for (let i = 0; i < lines.length;) {
    const line = lines[i]!.trim();
    if (!line) {
      i++;
      continue;
    }
    if (line.startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i]!.trim().startsWith('|')) {
        const cells = tableCells(lines[i++]!);
        if (!cells.every((cell) => /^[-:\s]+$/.test(cell))) rows.push(cells);
      }
      blocks.push(
        <div
          key={i}
          className="table-scroll"
          role="region"
          aria-label="Control reference"
          tabIndex={0}
        >
          <table className="table">
            <thead>
              <tr>
                {rows[0]?.map((cell, n) => (
                  <th key={n} scope="col">
                    {inline(cell.trim())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((row, n) => (
                <tr key={n}>
                  {row.map((cell, c) => (
                    <td key={c}>{inline(cell.trim())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    const image = /^!\[([^\]]*)\]\((images\/[a-zA-Z0-9_.-]+)\)$/.exec(line);
    if (image) {
      blocks.push(
        <img
          key={i}
          className="guide-screenshot"
          loading="lazy"
          alt={image[1]}
          src={`/user-guide/${image[2]}`}
        />,
      );
      i++;
      continue;
    }
    const heading = /^#{3,4} (.+)$/.exec(line);
    if (heading) {
      blocks.push(<h3 key={i}>{inline(heading[1]!)}</h3>);
      i++;
      continue;
    }
    if (/^\d+\. /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i]!.trim())) {
        items.push(lines[i++]!.trim().replace(/^\d+\. /, ''));
      }
      blocks.push(
        <ol key={i}>
          {items.map((item, n) => (
            <li key={n}>{inline(item)}</li>
          ))}
        </ol>,
      );
      continue;
    }
    const paragraph: string[] = [];
    while (i < lines.length && lines[i]!.trim()) {
      if (paragraph.length && /^(\||!\[|#{3,4} |\d+\. )/.test(lines[i]!.trim())) break;
      paragraph.push(lines[i++]!.trim());
    }
    blocks.push(<p key={i}>{inline(paragraph.join(' '))}</p>);
  }
  return <div className="guide-prose">{blocks}</div>;
}
