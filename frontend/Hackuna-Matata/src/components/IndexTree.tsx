import { useMemo, useState } from 'react';
import type { HierarchyNode } from '@/types/apiTypes';
import { nodeTitle } from '@/utils/nodeTitle';
import { computeNumbering } from '@/utils/treeWalk';

interface IndexTreeProps {
  node: HierarchyNode;
  depth?: number;
  selectedNodeId: string | null;
  onSelect: (node: HierarchyNode) => void;
  /** Numbering map keyed by node_id. Computed at the top-level call from
   *  the root and threaded through recursive calls — recomputing per
   *  recursion would lose the global ordering. */
  numbering?: Map<string, string>;
}

/** Recursive collapsible tree view of an IndexOutput.
 *  Internal nodes are clickable + expandable; leaf paragraphs show a snippet. */
export function IndexTree({
  node, depth = 0, selectedNodeId, onSelect, numbering,
}: IndexTreeProps) {
  const [expanded, setExpanded] = useState(depth < 2);  // first two levels open by default
  const isLeaf = !node.children || node.children.length === 0;
  const isRoot = node.kind === 'root';
  const isSelected = node.node_id === selectedNodeId;
  // Section-like nodes (anything that isn't a paragraph leaf) are bolded —
  // indentation alone already conveys hierarchy, so we don't need a [kind] tag.
  const isSection = node.kind !== 'paragraph';

  // Compute the numbering map once at the top of the recursion if the
  // caller didn't provide one; the same Map is then threaded down.
  const resolvedNumbering = useMemo(
    () => numbering ?? (isRoot ? computeNumbering(node) : new Map<string, string>()),
    [numbering, isRoot, node],
  );

  const indent = depth * 16;
  const num = resolvedNumbering.get(node.node_id);

  // Root: skip rendering itself, only render children
  if (isRoot) {
    return (
      <div>
        {(node.children || []).map((c) => (
          <IndexTree
            key={c.node_id}
            node={c}
            depth={depth}
            selectedNodeId={selectedNodeId}
            onSelect={onSelect}
            numbering={resolvedNumbering}
          />
        ))}
      </div>
    );
  }

  return (
    <div style={{ marginLeft: indent }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 6,
          padding: '4px 6px',
          background: isSelected ? '#e8f4fd' : 'transparent',
          borderRadius: 4,
          cursor: 'pointer',
          fontSize: 14,
        }}
        onClick={() => onSelect(node)}
      >
        {!isLeaf && (
          <span
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            style={{
              cursor: 'pointer',
              userSelect: 'none',
              minWidth: 12,
              color: '#888',
            }}
          >
            {expanded ? '▾' : '▸'}
          </span>
        )}
        {isLeaf && <span style={{ minWidth: 12 }}>•</span>}
        <span style={{
          flex: 1,
          fontWeight: isSection ? 600 : 400,
          color: isSection ? '#222' : '#555',
        }}>
          {num && (
            <span style={{
              color: '#789', fontVariantNumeric: 'tabular-nums', marginRight: 6,
            }}>
              {num}
            </span>
          )}
          {nodeTitle(node)}
        </span>
      </div>
      {expanded && !isLeaf && (
        <div>
          {(node.children || []).map((c) => (
            <IndexTree
              key={c.node_id}
              node={c}
              depth={depth + 1}
              selectedNodeId={selectedNodeId}
              onSelect={onSelect}
              numbering={resolvedNumbering}
            />
          ))}
        </div>
      )}
    </div>
  );
}
