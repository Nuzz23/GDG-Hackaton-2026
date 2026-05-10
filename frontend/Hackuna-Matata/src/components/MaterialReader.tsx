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
  /** Active highlight color (hex/CSS). When set, finishing a selection in
   *  the reader paints that selection with the color. `null` disables. */
  highlightColor?: string | null;
  /** When true, single-clicks on a word inside the reader toggle bold on
   *  that word ("classic highlighter" mode for keywords). */
  keywordsMode?: boolean;
  /** When set, all highlights and bold mutations are persisted to
   *  localStorage under this id and rehydrated on mount/material change. */
  materialId?: number | null;
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
  highlightColor = null,
  keywordsMode = false,
  materialId = null,
}: MaterialReaderProps) {
  const items = useMemo(() => linearizeTree(tree), [tree]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ── Annotation persistence (highlights + keyword bolding) ──────────────
  // We mutate the DOM directly via execCommand. To survive page reloads /
  // material switches, we serialise each modified item's innerHTML to
  // localStorage under `reader_annotations:{materialId}`, keyed by node_id.
  // On mount (and whenever the tree or materialId changes) we rehydrate
  // by reading the map and replacing each item's innerHTML.
  const storageKey = materialId != null ? `reader_annotations:${materialId}` : null;

  const loadAnnotations = (): Record<string, string> => {
    if (!storageKey) return {};
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  };

  const saveAnnotation = (nodeId: string, html: string) => {
    if (!storageKey || !nodeId) return;
    const map = loadAnnotations();
    map[nodeId] = html;
    try {
      localStorage.setItem(storageKey, JSON.stringify(map));
    } catch {
      /* quota / private mode — silently drop */
    }
  };

  // Rehydrate after items render. We wait one frame so React has finished
  // mounting the headings/paragraphs into the DOM, then walk the saved map
  // and replace the innerHTML for each known node_id.
  useEffect(() => {
    const root = scrollRef.current;
    if (!root || !storageKey) return;
    const ann = loadAnnotations();
    if (Object.keys(ann).length === 0) return;
    const apply = () => {
      for (const [nodeId, html] of Object.entries(ann)) {
        const el = root.querySelector<HTMLElement>(`[id="${cssEscapeId(nodeId)}"]`);
        if (el) el.innerHTML = html;
      }
    };
    requestAnimationFrame(apply);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, storageKey]);

  // ── Highlighting & keyword bolding ─────────────────────────────────────
  // We piggyback on the browser's native execCommand for both effects.
  // The reader is contentEditable=true (input is blocked via onBeforeInput),
  // which lets the user select text and lets execCommand mutate it without
  // any manual range/span juggling on our side. The reader doesn't re-render
  // headings/paragraphs (their items list is memoised on `tree`), so the
  // DOM mutations stick across scroll-driven prop changes.
  useEffect(() => {
    const root = scrollRef.current;
    if (!root) return;

    // Apply highlight color when the user finishes a selection.
    const onMouseUp = () => {
      if (!highlightColor) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) return;
      // Bail if the selection isn't entirely inside the reader.
      const anchor = sel.anchorNode;
      if (!anchor || !root.contains(anchor)) return;
      // Find the item element (paragraph/heading) we're about to mutate so
      // we can serialise & persist its innerHTML right after the command.
      const itemEl = closestItemEl(anchor, root);
      try {
        // styleWithCSS=true makes hiliteColor emit inline `style` instead of
        // <font> tags — easier to reason about and matches modern browsers.
        document.execCommand('styleWithCSS', false, 'true');
        document.execCommand('hiliteColor', false, highlightColor);
        sel.removeAllRanges();
        if (itemEl?.id) saveAnnotation(itemEl.id, itemEl.innerHTML);
      } catch {
        /* execCommand is deprecated but still supported; nothing to do on failure */
      }
    };

    // Toggle bold either on the current selection (if any) or on the word
    // under the click point.
    const onClick = (ev: MouseEvent) => {
      if (!keywordsMode) return;
      const sel = window.getSelection();

      // If text is already selected inside the reader, just bold the selection.
      if (sel && !sel.isCollapsed && sel.anchorNode && root.contains(sel.anchorNode)) {
        const itemEl = closestItemEl(sel.anchorNode, root);
        try {
          document.execCommand('styleWithCSS', false, 'true');
          document.execCommand('bold');
          if (itemEl?.id) saveAnnotation(itemEl.id, itemEl.innerHTML);
        } catch { /* ignore */ }
        return;
      }

      // Otherwise: expand the caret at click point to the word it's over,
      // then bold it. caretRangeFromPoint isn't on the standard TS DOM lib
      // for all targets, hence the cast.
      const doc: any = document;
      let range: Range | null = null;
      if (typeof doc.caretRangeFromPoint === 'function') {
        range = doc.caretRangeFromPoint(ev.clientX, ev.clientY);
      } else if (typeof doc.caretPositionFromPoint === 'function') {
        const pos = doc.caretPositionFromPoint(ev.clientX, ev.clientY);
        if (pos && pos.offsetNode) {
          range = document.createRange();
          range.setStart(pos.offsetNode, pos.offset);
          range.collapse(true);
        }
      }
      if (!range) return;
      const node = range.startContainer;
      if (node.nodeType !== Node.TEXT_NODE) return;
      const text = (node.nodeValue ?? '');
      const offset = range.startOffset;
      // Find word boundaries around the offset.
      const left = text.slice(0, offset).search(/\S+$/);
      const rightMatch = text.slice(offset).match(/^\S*/);
      const start = left === -1 ? offset : left;
      const end = offset + (rightMatch ? rightMatch[0].length : 0);
      if (end <= start) return;
      const wordRange = document.createRange();
      wordRange.setStart(node, start);
      wordRange.setEnd(node, end);
      const sel2 = window.getSelection();
      if (!sel2) return;
      sel2.removeAllRanges();
      sel2.addRange(wordRange);
      const itemEl = closestItemEl(node, root);
      try {
        document.execCommand('styleWithCSS', false, 'true');
        document.execCommand('bold');
        if (itemEl?.id) saveAnnotation(itemEl.id, itemEl.innerHTML);
      } catch { /* ignore */ }
      sel2.removeAllRanges();
    };

    root.addEventListener('mouseup', onMouseUp);
    root.addEventListener('click', onClick);
    return () => {
      root.removeEventListener('mouseup', onMouseUp);
      root.removeEventListener('click', onClick);
    };
  }, [highlightColor, keywordsMode]);

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
      // contentEditable lets us drive native selection + execCommand for
      // highlight/bold. We block all actual input so the document stays
      // read-only — the user can select + paint, but not type or delete.
      contentEditable
      suppressContentEditableWarning
      spellCheck={false}
      onBeforeInput={(e) => e.preventDefault()}
      onPaste={(e) => e.preventDefault()}
      onDrop={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        // Allow navigation / selection keys; block anything that would mutate.
        const allowed = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
          'Home', 'End', 'PageUp', 'PageDown', 'Tab', 'Escape'];
        if (!allowed.includes(e.key) && !(e.ctrlKey || e.metaKey)) {
          e.preventDefault();
        }
      }}
      style={{
        height: '100%',
        overflowY: 'auto',
        padding: '0 8px 80px 8px',
        boxSizing: 'border-box',
        scrollBehavior: 'smooth',
        // Hide the contentEditable focus outline; the user shouldn't perceive
        // this area as a text field.
        outline: 'none',
        cursor: keywordsMode ? 'pointer' : (highlightColor ? 'text' : 'auto'),
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

/**
 * Walk up from `node` until we hit an element with an `id` attribute (the
 * paragraph/heading element a node_id is rendered on). Returns null if
 * we reach `root` without finding one — selection happened to be in a
 * non-itemised area, nothing to persist.
 */
function closestItemEl(node: Node, root: Element): HTMLElement | null {
  let cur: Node | null = node;
  while (cur && cur !== root) {
    if (cur.nodeType === Node.ELEMENT_NODE && (cur as HTMLElement).id) {
      return cur as HTMLElement;
    }
    cur = cur.parentNode;
  }
  return null;
}
