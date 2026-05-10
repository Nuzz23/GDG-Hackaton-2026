import { useState } from 'react';
import type { HierarchyNode } from '@/types/apiTypes';
import { nodeTitle } from '@/utils/nodeTitle';

interface IndexTreeProps {
  node: HierarchyNode;
  depth?: number;
  selectedNodeId: string | null;
  onSelect: (node: HierarchyNode) => void;
}

/** Recursive collapsible tree view of an IndexOutput.
 *  Internal nodes are clickable + expandable; leaf paragraphs show a snippet. */
export function IndexTree({ node, depth = 0, selectedNodeId, onSelect }: IndexTreeProps) {
  const [expanded, setExpanded] = useState(depth < 2);  // first two levels open by default
  const isLeaf = !node.children || node.children.length === 0;
  const isRoot = node.kind === 'root';
  const isSelected = node.node_id === selectedNodeId;

  const indent = depth * 16;

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
        <span style={{ flex: 1 }}>
          <span style={{
            color: '#888', fontSize: 11, fontFamily: 'monospace', marginRight: 6,
          }}>
            [{node.kind}]
          </span>
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
            />
          ))}
        </div>
      )}
    </div>
  );
}
