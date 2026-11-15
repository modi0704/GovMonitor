import type { OfficeRow } from '../../api/types';

export interface TreeNode extends OfficeRow {
  children: TreeNode[];
}

/** Build a forest from the flat, tree-ordered list. Offices whose parent is not visible are roots. */
export function buildTree(rows: OfficeRow[]): TreeNode[] {
  const nodes = new Map<string, TreeNode>();
  rows.forEach((r) => nodes.set(r.id, { ...r, children: [] }));
  const roots: TreeNode[] = [];
  rows.forEach((r) => {
    const node = nodes.get(r.id)!;
    const parent = r.parent_id ? nodes.get(r.parent_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  });
  return roots;
}

/** Ids of an office and everything beneath it. */
export function subtreeIds(rows: OfficeRow[], id: string): Set<string> {
  const out = new Set([id]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const r of rows) {
      if (r.parent_id && out.has(r.parent_id) && !out.has(r.id)) {
        out.add(r.id);
        grew = true;
      }
    }
  }
  return out;
}
