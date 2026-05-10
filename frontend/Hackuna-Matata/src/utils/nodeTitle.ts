import type { HierarchyNode } from '@/types/apiTypes';

/**
 * Pick a human-readable title for an index node.
 *
 * Priority:
 *   1. label  → use as-is (chapters/sections/subsections set by the indexer)
 *   2. text   → first ~60 characters with newlines collapsed (leaf paragraphs)
 *   3. kind   → "Paragraph" / "Section" capitalised — last-resort fallback
 *
 * Never returns the raw `node_id` (n_x_y is internal — not user-facing).
 */
export function nodeTitle(node: HierarchyNode, maxLen: number = 60): string {
  if (node.label && node.label.trim()) {
    return node.label.trim();
  }
  if (node.text && node.text.trim()) {
    const flat = node.text.trim().replace(/\s+/g, ' ');
    return flat.length <= maxLen ? flat : flat.slice(0, maxLen - 1) + '…';
  }
  // Last resort — capitalise the kind
  const k = node.kind || 'paragraph';
  return k.charAt(0).toUpperCase() + k.slice(1);
}
