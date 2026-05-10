import { useEffect, useMemo, useRef } from 'react';
import type { HierarchyNode } from '@/types/apiTypes';
import { linearizeTree } from '@/utils/treeWalk';

interface MaterialReaderProps {
  /** Root of the index tree to render. */
  tree: HierarchyNode;
  /** Called whenever the topmost visible heading changes. */
  onCurrentNodeChange: (nodeId: string) => void;
  /** When this changes, the reader scrolls to that heading. */
  scrollToNodeId?: string | null;
}

/**
 * Long-form reader: renders the whole document linearly with collapsible
 * headings, then watches the scroll position to report which heading is
 * currently "in focus" (topmost in viewport, with a small offset). The
 * parent uses that to update the breadcrumb shown above the reader.
 *
 * Heading IDs match `node_id`s, so scrolling to a node and observing
 * which one is current are both keyed off the same identifier.
 */
export function MaterialReader({
  tree,
  onCurrentNodeChange,
  scrollToNodeId,
}: MaterialReaderProps) {
  const items = useMemo(() => linearizeTree(tree), [tree]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Set up an IntersectionObserver that fires whenever a heading enters /
  // leaves the top 20% of the scroll viewport. We pick the topmost
  // intersecting heading as "current".
  useEffect(() => {
    const root = scrollRef.current;
    if (!root) return;

    const headings = Array.from(root.querySelectorAll<HTMLElement>('[data-heading]'));
    if (headings.length === 0) return;

    let lastReported: string | null = null;

    const recompute = () => {
      // The "current" heading is the one whose top edge is highest while
      // still above a small threshold from the scroll-container top.
      const containerTop = root.getBoundingClientRect().top;
      const threshold = containerTop + 80; // ~80px below container top
      let candidate: HTMLElement | null = null;
      for (const h of headings) {
        const top = h.getBoundingClientRect().top;
        if (top <= threshold) {
          candidate = h;
        } else {
          break;
        }
      }
      const id = candidate?.id || headings[0].id;
      if (id && id !== lastReported) {
        lastReported = id;
        onCurrentNodeChange(id);
      }
    };

    // Initial report once layout has settled.
    requestAnimationFrame(recompute);

    const onScroll = () => recompute();
    root.addEventListener('scroll', onScroll, { passive: true });
    return () => root.removeEventListener('scroll', onScroll);
  }, [items, onCurrentNodeChange]);

  // Programmatic scroll: when scrollToNodeId changes, jump to that heading.
  useEffect(() => {
    if (!scrollToNodeId) return;
    const root = scrollRef.current;
    if (!root) return;
    const target = root.querySelector<HTMLElement>(`[id="${cssEscapeId(scrollToNodeId)}"]`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [scrollToNodeId]);

  return (
    <div
      ref={scrollRef}
      style={{
        height: '100%',
        overflowY: 'auto',
        padding: '0 8px 80px 8px',
        boxSizing: 'border-box',
        scrollBehavior: 'smooth',
      }}
    >
      {items.length === 0 && (
        <p style={{ color: '#888', fontStyle: 'italic' }}>
          (no readable content in this index)
        </p>
      )}
      {items.map((item) => {
        if (item.kind === 'heading') {
          const Tag = item.level === 1 ? 'h1' : item.level === 2 ? 'h2' : 'h3';
          return (
            <Tag
              key={item.node_id}
              id={item.node_id}
              data-heading="1"
              data-node-kind={item.nodeKind}
              style={{
                marginTop: item.level === 1 ? '1.6em' : '1.2em',
                marginBottom: '0.4em',
                color: '#222',
                lineHeight: 1.25,
                fontSize: item.level === 1 ? '1.55em' : item.level === 2 ? '1.25em' : '1.05em',
                fontWeight: 700,
              }}
            >
              {item.numbering && (
                <span style={{
                  color: '#789', fontWeight: 600, marginRight: '0.5em',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {item.numbering}
                </span>
              )}
              {item.label}
            </Tag>
          );
        }
        // paragraph
        return (
          <p
            key={item.node_id}
            id={item.node_id}
            style={{
              margin: '0.6em 0',
              color: '#333',
              lineHeight: 1.55,
              fontSize: '0.97em',
              whiteSpace: 'pre-wrap',
            }}
          >
            {item.text}
          </p>
        );
      })}
    </div>
  );
}

function cssEscapeId(id: string): string {
  // Minimal escape — node_ids are alnum + underscore + hyphen in our
  // schemas, so we don't need full CSS.escape. Defensive nonetheless.
  return id.replace(/(["\\])/g, '\\$1');
}
