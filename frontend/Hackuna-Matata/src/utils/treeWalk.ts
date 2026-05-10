import type { HierarchyNode } from '@/types/apiTypes';

/* ──────────────────────────────────────────────────────────────────────────
 *  Tree linearisation for the reading view
 * ────────────────────────────────────────────────────────────────────────── */

export type ReaderItem =
  | { kind: 'heading'; level: 1 | 2 | 3; label: string; node_id: string; nodeKind: string }
  | { kind: 'paragraph'; text: string; node_id: string };

/**
 * Walk the tree in document order producing a flat list of render items:
 * one heading per chapter/section/subsection (with `node_id` for scroll &
 * intersection tracking), one paragraph item per leaf paragraph (with `text`).
 *
 * Root is skipped (never rendered as a heading). Internal nodes with no
 * label are skipped too — we don't want empty headings cluttering the doc.
 */
export function linearizeTree(node: HierarchyNode): ReaderItem[] {
  const out: ReaderItem[] = [];
  walk(node, out);
  return out;
}

function walk(node: HierarchyNode, out: ReaderItem[]): void {
  if (!node) return;
  const kind = node.kind;

  if (kind === 'root') {
    for (const c of node.children || []) walk(c, out);
    return;
  }

  const isLeaf = !node.children || node.children.length === 0;

  if (isLeaf) {
    if (kind === 'paragraph' && node.text && node.text.trim()) {
      out.push({ kind: 'paragraph', text: node.text, node_id: node.node_id });
    }
    return;
  }

  // Internal node — emit a heading then recurse.
  if (node.label && node.label.trim()) {
    out.push({
      kind: 'heading',
      level: levelForKind(kind),
      label: node.label.trim(),
      node_id: node.node_id,
      nodeKind: kind,
    });
  }
  for (const c of node.children || []) walk(c, out);
}

function levelForKind(kind: string): 1 | 2 | 3 {
  if (kind === 'chapter') return 1;
  if (kind === 'section') return 2;
  return 3; // subsection or anything else
}


/* ──────────────────────────────────────────────────────────────────────────
 *  Tree navigation helpers
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Return the path from root to the node with `targetId` (inclusive on both
 * ends). The root itself is included as the first entry.
 *
 * Used to compute the breadcrumb shown above the reader.
 */
export function findPath(
  node: HierarchyNode,
  targetId: string,
  trail: HierarchyNode[] = []
): HierarchyNode[] | null {
  const next = [...trail, node];
  if (node.node_id === targetId) return next;
  for (const c of node.children || []) {
    const hit = findPath(c, targetId, next);
    if (hit) return hit;
  }
  return null;
}


/**
 * From the given path (root → ... → current), return the closest ancestor
 * that is **not** a paragraph leaf — i.e. a chapter/section/subsection
 * node we can meaningfully generate a quiz for.
 *
 * Why: the reader tracks the topmost visible heading via IntersectionObserver
 * and that's already a non-paragraph node. But if a caller hands us a path
 * to a paragraph leaf (e.g. user clicks a leaf in the tree), we want to
 * promote to its parent so the quiz has substantive text.
 */
export function nearestSectionAncestor(path: HierarchyNode[]): HierarchyNode | null {
  for (let i = path.length - 1; i >= 0; i--) {
    const n = path[i];
    if (n.kind !== 'paragraph' && n.kind !== 'root') return n;
  }
  return null;
}


/**
 * Format a path as a breadcrumb-friendly array of label segments.
 * Skips the root (it has no label) and any segments without a label.
 */
export function pathLabels(path: HierarchyNode[] | null): string[] {
  if (!path) return [];
  return path
    .filter(n => n.kind !== 'root' && n.label && n.label.trim())
    .map(n => n.label!.trim());
}
