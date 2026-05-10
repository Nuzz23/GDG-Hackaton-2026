import { useEffect, useMemo, useState } from 'react';
import { agentApi } from '@/services/api';
import type { IndexOutput } from '@/types/apiTypes';
import { MaterialReader } from './MaterialReader';
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
      {/* Top bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '14px 24px', borderBottom: '1px solid #e6e8eb', background: 'white',
      }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>📚 {materialName}</h2>
        <button onClick={onBack} style={{
          padding: '6px 12px', cursor: 'pointer',
          border: '1px solid #ccc', background: 'white', borderRadius: 4,
        }}>
          ← Back
        </button>
      </div>

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
            </div>

            {/* Reader */}
            <div style={{ flex: 1, minHeight: 0, padding: '8px 18px' }}>
              <MaterialReader
                tree={index.tree}
                onCurrentNodeChange={onCurrentNodeChange}
                scrollToNodeId={scrollTargetId}
              />
            </div>
          </div>

          {/* ── Right: Session side panel (with quiz CTA at the bottom) ── */}
          <div style={{
            background: 'white', border: '1px solid #e6e8eb', borderRadius: 10,
            display: 'flex', flexDirection: 'column', minHeight: 0,
          }}>
            <div style={{ padding: 14, overflowY: 'auto', flex: 1, minHeight: 0 }}>
              <h3 style={{ marginTop: 0, fontSize: '0.95rem' }}>Session</h3>
              <p style={{ fontSize: 12, color: '#789', lineHeight: 1.5 }}>
                Scroll through the material — the breadcrumb above and the
                index on the left both track your position.
              </p>
              <div style={{
                marginTop: 16, padding: 10, background: '#f5f8fb',
                borderRadius: 6, fontSize: 11, color: '#456',
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Tip</div>
                The quiz scope defaults to the section currently in view.
                The button below opens a popup where you can also pick a
                different section, a paragraph, or the whole document.
              </div>
            </div>

            {/* Sticky bottom CTA — almost as wide as the panel, height 59px. */}
            <div style={{
              padding: '0.5rem 0.75rem 0.75rem',
              borderTop: '1px solid rgba(0,0,0,0.08)',
              flexShrink: 0,
            }}>
              <button
                onClick={onOpenQuiz}
                disabled={!canOpenQuiz}
                style={{
                  width: '100%', height: 59, borderRadius: '0.7rem',
                  background: canOpenQuiz ? '#27ae60' : '#a8c9b3',
                  color: 'white', border: 'none',
                  fontSize: '1rem', fontWeight: 700,
                  cursor: canOpenQuiz ? 'pointer' : 'not-allowed',
                }}
              >
                Test my knowledges
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
