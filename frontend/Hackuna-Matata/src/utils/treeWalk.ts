import type { HierarchyNode } from '@/types/apiTypes';

/* ──────────────────────────────────────────────────────────────────────────
 *  Hierarchical numbering   (1 / 1.1 / 1.1.I / 1.1.I.a / …)
 * ────────────────────────────────────────────────────────────────────────── */

function toRoman(n: number): string {
  const table: [string, number][] = [
    ['M', 1000], ['CM', 900], ['D', 500], ['CD', 400],
    ['C', 100],  ['XC', 90],  ['L', 50],  ['XL', 40],
    ['X', 10],   ['IX', 9],   ['V', 5],   ['IV', 4],
    ['I', 1],
  ];
  let s = '';
  for (const [sym, v] of table) {
    while (n >= v) { s += sym; n -= v; }
  }
  return s;
}

function toAlpha(n: number): string {
  // 1 → a, 26 → z, 27 → aa, 28 → ab …
  let s = '';
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(97 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

/**
 * Format a single numbering segment by depth (1-indexed: depth=1 is the
 * top-level child of the root). The user-requested scheme is:
 *   depth 1  → arabic   (1, 2, 3)
 *   depth 2  → arabic   (1.1, 1.2)
 *   depth 3  → roman    (1.1.I, 1.1.II)
 *   depth ≥4 → lowercase letters (1.1.I.a, 1.1.I.b)
 */
function formatLevel(n: number, depth: number): string {
  if (depth <= 2) return String(n);
  if (depth === 3) return toRoman(n);
  return toAlpha(n);
}

/**
 * Walk the tree assigning a numbering string ("1.1.I.a") to every non-root
 * node based on its position among siblings. The root itself is excluded.
 *
 * Returned as a Map keyed by `node_id`, so every consumer (IndexTree,
 * MaterialReader, QuizModal picker) can render the same numbers without
 * having to re-walk the tree.
 */
export function computeNumbering(root: HierarchyNode): Map<string, string> {
  const out = new Map<string, string>();
  const walk = (node: HierarchyNode, path: number[]): void => {
    if (node.kind === 'root') {
      (node.children || []).forEach((c, i) => walk(c, [i + 1]));
      return;
    }
    const numbering = path.map((n, i) => formatLevel(n, i + 1)).join('.');
    out.set(node.node_id, numbering);
    (node.children || []).forEach((c, i) => walk(c, [...path, i + 1]));
  };
  walk(root, []);
  return out;
}


/* ──────────────────────────────────────────────────────────────────────────
 *  Tree linearisation for the reading view
 * ────────────────────────────────────────────────────────────────────────── */

export type ReaderItem =
  | { kind: 'heading'; level: 1 | 2 | 3; label: string; numbering: string; node_id: string; nodeKind: string }
  | { kind: 'paragraph'; text: string; numbering: string; node_id: string };

/**
 * Walk the tree in document order producing a flat list of render items:
 * one heading per chapter/section/subsection (with `node_id` for scroll &
 * intersection tracking), one paragraph item per leaf paragraph (with `text`).
 *
 * Root is skipped (never rendered as a heading). Internal nodes with no
 * label are skipped too — we don't want empty headings cluttering the doc.
 */
export function linearizeTree(node: HierarchyNode): ReaderItem[] {
  const numbering = computeNumbering(node);
  const out: ReaderItem[] = [];
  walk(node, out, numbering);
  return out;
}

function walk(node: HierarchyNode, out: ReaderItem[], numbering: Map<string, string>): void {
  if (!node) return;
  const kind = node.kind;

  if (kind === 'root') {
    for (const c of node.children || []) walk(c, out, numbering);
    return;
  }

  const isLeaf = !node.children || node.children.length === 0;
  const num = numbering.get(node.node_id) ?? '';

  if (isLeaf) {
    if (kind === 'paragraph' && node.text && node.text.trim()) {
      out.push({ kind: 'paragraph', text: node.text, numbering: num, node_id: node.node_id });
    }
    return;
  }

  // Internal node — emit a heading then recurse.
  if (node.label && node.label.trim()) {
    out.push({
      kind: 'heading',
      level: levelForKind(kind),
      label: node.label.trim(),
      numbering: num,
      node_id: node.node_id,
      nodeKind: kind,
    });
  }
  for (const c of node.children || []) walk(c, out, numbering);
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
 * Collect the node_id of `node` and every descendant under it, in
 * document order. Used by the QuizModal multi-select to implement the
 * cascading "click section → tick everything below" behavior.
 */
export function collectSubtreeIds(node: HierarchyNode): string[] {
  const out: string[] = [];
  const walk = (n: HierarchyNode) => {
    if (n.node_id) out.push(n.node_id);
    for (const c of n.children || []) walk(c);
  };
  walk(node);
  return out;
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


/* ──────────────────────────────────────────────────────────────────────────
 *  Picker flattening (used by QuizModal's section/paragraph dropdown)
 * ────────────────────────────────────────────────────────────────────────── */

export interface PickerEntry {
  node: HierarchyNode;
  depth: number;       // 0 = root, 1 = chapter, ...
  label: string;       // pre-formatted with leading indent
  isRoot: boolean;
}

/**
 * Walk the tree producing a flat list suitable for an HTML <select>: the
 * root is included first as "All document", then every section and
 * paragraph leaf in document order. We indent labels with leading spaces
 * so the dropdown still conveys the hierarchy.
 *
 * Paragraph text is truncated to ~60 chars; sections show their label
 * (or a "Section" fallback if unlabelled, which shouldn't happen in
 * practice — the indexer always assigns labels to internal nodes).
 */
export function flattenForPicker(root: HierarchyNode): PickerEntry[] {
  const out: PickerEntry[] = [];
  const numbering = computeNumbering(root);

  out.push({
    node: root,
    depth: 0,
    label: 'All document',
    isRoot: true,
  });

  const walkPicker = (n: HierarchyNode, depth: number) => {
    if (n.kind === 'root') {
      for (const c of n.children || []) walkPicker(c, depth + 1);
      return;
    }
    const indent = '  '.repeat(Math.max(0, depth - 1));
    let title: string;
    if (n.label && n.label.trim()) {
      title = n.label.trim();
    } else if (n.text && n.text.trim()) {
      const flat = n.text.trim().replace(/\s+/g, ' ');
      title = flat.length <= 60 ? flat : flat.slice(0, 59) + '…';
    } else {
      title = n.kind.charAt(0).toUpperCase() + n.kind.slice(1);
    }
    const num = numbering.get(n.node_id);
    const prefix = num ? `${num}. ` : '';
    out.push({
      node: n,
      depth,
      label: indent + prefix + title,
      isRoot: false,
    });
    for (const c of n.children || []) walkPicker(c, depth + 1);
  };

  walkPicker(root, 0);
  return out;
}
