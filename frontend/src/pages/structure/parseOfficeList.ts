/**
 * Parse a pasted list of offices (P2.3). One office per line:
 *
 *   CODE <tab> Name                    — indentation (tabs, or every 2 spaces) sets the parent
 *   CODE <tab> Name <tab> PARENT-CODE  — an explicit parent code overrides indentation
 *
 * " - " or "," may be used instead of a tab. Blank lines are skipped. Text copied from Excel
 * arrives tab-separated, so a two- or three-column range pastes as-is. Excel puts nothing
 * before the first column, so to show depth there, put the codes in column B, C, ... instead.
 */
export interface ParsedRow {
  line: number;
  code: string;
  name: string;
  depth: number;
  parent_code?: string;
}

export function parseOfficeList(text: string): ParsedRow[] {
  const rows: ParsedRow[] = [];
  text.split(/\r?\n/).forEach((raw, index) => {
    if (!raw.trim()) return;
    // Depth from leading whitespace: each tab or each pair of spaces is one level.
    const lead = raw.match(/^[\t ]*/)?.[0] ?? '';
    const depth =
      (lead.match(/\t/g)?.length ?? 0) + Math.floor((lead.match(/ /g)?.length ?? 0) / 2);
    const body = raw.slice(lead.length);
    let parts: string[];
    if (body.includes('\t')) parts = body.split('\t');
    else if (body.includes(' - ')) parts = body.split(' - ');
    else if (body.includes(',')) parts = body.split(',');
    else parts = [body];
    parts = parts.map((p) => p.trim());
    while (parts.length > 1 && parts[parts.length - 1] === '') parts.pop();
    const [code = '', name = '', parent = ''] = parts;
    const row: ParsedRow = { line: index + 1, code, name, depth };
    if (parent) row.parent_code = parent;
    rows.push(row);
  });
  return rows;
}
