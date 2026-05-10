import { useEffect, useMemo, useState } from 'react';
import { agentApi } from '@/services/api';
import type { IndexOutput } from '@/types/apiTypes';
import { MaterialReader } from './MaterialReader';
import { ChatPanel } from './ChatPanel';
import { findPath, pathLabels } from '@/utils/treeWalk';

interface MaterialDetailViewProps {
  groupId: number;
  materialId: number;
  materialName: string;
  onBack: () => void;

  /** Lifted-up index state — owned by HomePage so the left sidebar can
   *  show the IndexTree in place of the John Doe profile panel. */
  index: IndexOutput | null;
  onIndexLoaded: (index: IndexOutput) => void;

  /** Heading currently topmost in the reader — set by us, read by HomePage
   *  to highlight the right node in the sidebar tree. */
  currentNodeId: string | null;
  onCurrentNodeChange: (id: string) => void;

  /** When HomePage's tree-click sets this, the reader scrolls to it. */
  scrollTargetId: string | null;

  /** Opens the QuizModal (lifted up to HomePage so the modal can overlay
   *  the whole page; we just trigger it from the right Session panel). */
  onOpenQuiz: () => void;
  /** Whether the quiz button is enabled (false until an index is loaded
   *  and a target node has been resolved). */
  canOpenQuiz: boolean;
}

type Phase = 'idle' | 'indexing' | 'index_ready';

/**
 * Two-column reading view (the index tree lives in HomePage's sidebar):
 *   ┌──────────────────────────────┬──────────┐
 *   │  Breadcrumb + Quiz button    │ (side)   │
 *   │  ───────────────────────     │          │
 *   │  Scrollable reader           │          │
 *   └──────────────────────────────┴──────────┘
 *
 * Scrolling the reader updates the breadcrumb live; when HomePage flips
 * `scrollTargetId`, the reader scrolls to that heading. The "Mettimi alla
 * prova" button opens a centered modal whose target is the closest
 * non-paragraph ancestor of the currently-visible heading.
 */
export function MaterialDetailView(props: MaterialDetailViewProps) {
  const {
    groupId, materialId, materialName, onBack,
    index, onIndexLoaded,
    currentNodeId, onCurrentNodeChange,
    scrollTargetId,
    onOpenQuiz, canOpenQuiz,
  } = props;

  const [phase, setPhase] = useState<Phase>(index ? 'index_ready' : 'idle');
  const [error, setError] = useState<string | null>(null);

  // ── Reader annotation tools ────────────────────────────────────────────
  // Highlight: when `highlightOpen` is true, the color toolbar appears below
  // the breadcrumb. `highlightColor` is the actively-armed color (the one
  // that will paint the next selection in the reader). Picking the same
  // color twice unarms it; closing the toolbar also unarms.
  const [highlightOpen, setHighlightOpen] = useState(false);
  const [highlightColor, setHighlightColor] = useState<string | null>(null);

  // Keywords: classic "highlighter pen" mode for bold. While ON, single
  // clicks on a word in the reader bold that word. The button click also
  // bolds the current selection if one exists, without flipping the mode.
  const [keywordsMode, setKeywordsMode] = useState(false);

  const toggleHighlightTool = () => {
    setHighlightOpen((prev) => {
      const next = !prev;
      if (!next) setHighlightColor(null); // closing the toolbar disarms
      return next;
    });
  };

  const pickHighlightColor = (color: string) => {
    setHighlightColor((prev) => (prev === color ? null : color));
  };

  const handleKeywordsClick = () => {
    // If the user has a live selection inside the reader, just bold it
    // without toggling the persistent mode. We use the preserved selection
    // (the button's onMouseDown→preventDefault keeps it alive). Otherwise
    // flip the click-to-bold mode.
    const sel = window.getSelection();
    const hasSelection = !!(sel && !sel.isCollapsed && sel.toString().trim().length > 0);
    if (hasSelection) {
      try {
        document.execCommand('styleWithCSS', false, 'true');
        document.execCommand('bold');
      } catch { /* ignore */ }
      return;
    }
    setKeywordsMode((prev) => !prev);
  };

  // On mount (or when materialId changes) try to load an existing index.
  // If HomePage already has it cached we skip the fetch.
  useEffect(() => {
    if (index) {
      setPhase('index_ready');
      return;
    }
    (async () => {
      try {
        const r = await agentApi.getLatestIndex(materialId);
        onIndexLoaded(r.data.index);
        setPhase('index_ready');
      } catch (e: any) {
        if (e?.response?.status !== 404) {
          setError(e?.message || 'Could not load existing index');
        }
        // 404 → no index yet → stay in idle
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [materialId]);

  const runIndexing = async () => {
    setError(null);
    setPhase('indexing');
    try {
      const r = await agentApi.indexMaterial(groupId, materialId);
      onIndexLoaded(r.data.index);
      setPhase('index_ready');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Indexing failed');
      setPhase('idle');
    }
  };

  // Path from root to the currently-visible heading — used here only for
  // the breadcrumb. The "Test my knowledges" button + QuizModal now live
  // in HomePage so the trigger can sit at the bottom of the Index sidebar.
  const currentPath = useMemo(() => {
    if (!index?.tree || !currentNodeId) return null;
    return findPath(index.tree, currentNodeId);
  }, [index, currentNodeId]);

  const breadcrumb = useMemo(() => pathLabels(currentPath), [currentPath]);

  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
      boxSizing: 'border-box', background: '#fafbfc',
    }}>
      {error && (
        <div style={{
          padding: 12, background: '#fdebee', borderLeft: '4px solid #c0392b',
          margin: 16, fontSize: 14, color: '#922',
        }}>
          ⚠ {error}
        </div>
      )}

      {/* PHASE: idle ───────────────────────────────────── */}
      {phase === 'idle' && (
        <div style={{ textAlign: 'center', padding: 60, flex: 1 }}>
          <p style={{ fontSize: 16, color: '#555', marginBottom: 20 }}>
            This material hasn't been indexed yet. The first step is to extract its hierarchical structure.
          </p>
          <button
            onClick={runIndexing}
            style={{
              padding: '12px 24px', fontSize: 16, background: '#3498db',
              color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer',
            }}
          >
            Index this material
          </button>
          <p style={{ marginTop: 16, fontSize: 12, color: '#888' }}>
            ⏱ PDFs take a few seconds; audio/video can take 1–3 minutes.
          </p>
        </div>
      )}

      {/* PHASE: indexing ──────────────────────────────── */}
      {phase === 'indexing' && (
        <div style={{ textAlign: 'center', padding: 60, flex: 1 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <p>Indexing in progress…</p>
          <p style={{ fontSize: 12, color: '#888' }}>
            processing_agent is parsing the file and extracting the structure.
          </p>
        </div>
      )}

      {/* PHASE: index_ready — 2-column layout (index tree is in HomePage sidebar) */}
      {phase === 'index_ready' && index && (
        <div style={{
          flex: 1, minHeight: 0,
          display: 'grid',
          gridTemplateColumns: '1fr 240px',
          gap: 16, padding: 16,
        }}>
          {/* ── Center: breadcrumb + button + reader ───── */}
          <div style={{
            background: 'white', border: '1px solid #e6e8eb', borderRadius: 10,
            display: 'flex', flexDirection: 'column', minHeight: 0,
          }}>
            {/* Breadcrumb header */}
            <div style={{
              padding: '14px 18px', borderBottom: '1px solid #eef0f2',
            }}>
              <div style={{ fontSize: 11, color: '#789', textTransform: 'uppercase', letterSpacing: 0.6 }}>
                Currently reading
              </div>
              <div style={{
                fontSize: 14, color: '#234', fontWeight: 600,
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {breadcrumb.length > 0 ? breadcrumb.join(' › ') : '—'}
              </div>

              {/* Color toolbar — visible only when the Highlight tool is open. */}
              {highlightOpen && (
                <div style={{
                  marginTop: 10, display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontSize: 11, color: '#789' }}>Highlighter:</span>
                  {HIGHLIGHT_COLORS.map((c) => {
                    const active = highlightColor === c.value;
                    return (
                      <button
                        key={c.value}
                        // Prevent the button from stealing focus / killing the
                        // current text selection in the reader.
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => pickHighlightColor(c.value)}
                        title={c.name}
                        aria-label={c.name}
                        style={{
                          width: 22, height: 22, borderRadius: '50%',
                          background: c.value,
                          border: active ? '2px solid #234' : '1px solid #c0c4c8',
                          boxShadow: active ? '0 0 0 2px white inset' : 'none',
                          cursor: 'pointer', padding: 0,
                        }}
                      />
                    );
                  })}
                  {highlightColor && (
                    <span style={{ fontSize: 11, color: '#456', marginLeft: 4 }}>
                      Drag-select to paint
                    </span>
                  )}
                </div>
              )}
              {keywordsMode && (
                <div style={{ marginTop: 8, fontSize: 11, color: '#456' }}>
                  ✏️ Keywords: click any word to toggle bold. Click the button again to exit.
                </div>
              )}
            </div>

            {/* Reader */}
            <div style={{ flex: 1, minHeight: 0, padding: '8px 18px' }}>
              <MaterialReader
                tree={index.tree}
                onCurrentNodeChange={onCurrentNodeChange}
                scrollToNodeId={scrollTargetId}
                highlightColor={highlightColor}
                keywordsMode={keywordsMode}
                materialId={materialId}
              />
            </div>
          </div>

          {/* ── Right column: Chat (top, collapsible) + Tools (bottom) ── */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0,
          }}>
            <ChatPanel />

            {/* ── Tools / Session panel (with quiz CTA at the bottom) ── */}
            <div style={{
              background: 'white', border: '1px solid #e6e8eb', borderRadius: 10,
              display: 'flex', flexDirection: 'column', minHeight: 0,
              flex: '0 0 auto',
            }}>
            <div style={{ padding: '14px 14px 4px', flexShrink: 0 }}>
              <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Tools</h3>
            </div>

            {/* All three CTAs share the same green pill style (per spec).
                Active state for Keywords/Highlight is conveyed by the
                indicators that appear under the breadcrumb header, not by
                the button color. The first two preserve the live text
                selection in the reader via onMouseDown→preventDefault. */}
            <div style={{
              padding: '0.5rem 0.75rem 0.75rem',
              flexShrink: 0,
              display: 'flex', flexDirection: 'column', gap: 8,
            }}>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={handleKeywordsClick}
                style={CTA_BUTTON}
              >
                Keywords
              </button>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={toggleHighlightTool}
                style={CTA_BUTTON}
              >
                Highlight
              </button>
              <button
                onClick={onOpenQuiz}
                disabled={!canOpenQuiz}
                style={{
                  ...CTA_BUTTON,
                  background: canOpenQuiz ? '#27ae60' : '#a8c9b3',
                  cursor: canOpenQuiz ? 'pointer' : 'not-allowed',
                }}
              >
                Test my knowledges
              </button>
            </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// Highlighter palette — soft pastel tints so dark text stays legible on top.
// Order matches the user's spec: red, yellow, green, blue, purple.
const HIGHLIGHT_COLORS: { name: string; value: string }[] = [
  { name: 'Red',    value: '#fab1a0' },
  { name: 'Yellow', value: '#ffeaa7' },
  { name: 'Green',  value: '#b8e994' },
  { name: 'Blue',   value: '#a8d5ff' },
  { name: 'Purple', value: '#d6b3ff' },
];

// Shared CTA button style — Keywords / Highlight / Test all use this so the
// three buttons look identical (per user spec). Per-button overrides (the
// disabled tint on the Test button) layer on top via spread.
const CTA_BUTTON: React.CSSProperties = {
  width: '100%', height: 59, borderRadius: '0.7rem',
  background: '#27ae60', color: 'white', border: 'none',
  fontSize: '1rem', fontWeight: 700, cursor: 'pointer',
};
