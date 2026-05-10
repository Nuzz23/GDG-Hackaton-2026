import { useEffect, useMemo, useState } from 'react';
import { agentApi } from '@/services/api';
import type {
  Difficulty, HierarchyNode, ItemTypeCode, QuizOutput,
} from '@/types/apiTypes';
import { QuizPlayer } from './QuizPlayer';
import { flattenForPicker, collectSubtreeIds, type PickerEntry } from '@/utils/treeWalk';

interface QuizModalProps {
  isOpen: boolean;
  onClose: () => void;
  materialId: number;
  /** The full index tree — used to populate the section/paragraph picker.
   *  Required so the user can override the auto-detected target. */
  tree: HierarchyNode | null;
  /** The node the quiz will be generated on by default — the reader feeds
   *  the currently-visible chapter/section here. The user can still pick
   *  a different node (or "All document") from the picker. */
  targetNode: HierarchyNode | null;
}

type Phase = 'form' | 'generating' | 'playing' | 'error';

/**
 * Centered popup that walks the user through:
 *   1. Form to pick item type, difficulty and N
 *   2. Spinner while the LLM generates
 *   3. QuizPlayer to answer the items, see interventions
 *
 * The "target node" is fixed when the modal opens, so the user can keep
 * reading other parts of the doc behind the modal without losing context.
 */
export function QuizModal({ isOpen, onClose, materialId, tree, targetNode }: QuizModalProps) {
  const [phase, setPhase] = useState<Phase>('form');
  const [error, setError] = useState<string | null>(null);
  const [quiz, setQuiz] = useState<QuizOutput | null>(null);
  const [quizArtifactId, setQuizArtifactId] = useState<number | null>(null);

  const [itemType, setItemType] = useState<ItemTypeCode>('qa');
  const [n, setN] = useState(3);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');

  // Picker entries — root ("All document") + all sections + paragraph leaves.
  const pickerEntries = useMemo(
    () => (tree ? flattenForPicker(tree) : []),
    [tree],
  );

  // The set of nodes the quiz will be generated on. Multi-select: the user
  // can tick any combination of sections and/or paragraphs. The backend
  // dedups ancestors, so it's harmless to leave a parent + its child both
  // checked, but the UX visually surfaces this so the user knows.
  const [pickedNodeIds, setPickedNodeIds] = useState<Set<string>>(new Set());

  // Reset to form whenever the modal is reopened with a (possibly new)
  // target node — we don't want stale quiz state lingering. We also
  // re-seed the picker selection from the new targetNode.
  useEffect(() => {
    if (isOpen) {
      setPhase('form');
      setError(null);
      setQuiz(null);
      setQuizArtifactId(null);
      // Seed with the auto-detected target (or root as a fallback).
      const seed = targetNode?.node_id ?? tree?.node_id ?? null;
      setPickedNodeIds(seed ? new Set([seed]) : new Set());
    }
  }, [isOpen, targetNode?.node_id, tree?.node_id]);

  // While the modal is open, lock background interaction:
  //   - body scroll off (prevents wheel/touch from scrolling the page)
  //   - blur whatever was focused (otherwise the reader's contentEditable
  //     keeps catching keyboard arrows / page-down behind the popup)
  useEffect(() => {
    if (!isOpen) return;
    const prevBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const active = document.activeElement as HTMLElement | null;
    if (active && typeof active.blur === 'function') active.blur();
    return () => {
      document.body.style.overflow = prevBodyOverflow;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  /**
   * Cascading toggle: clicking on a section ticks/unticks every node in
   * its subtree (including the section itself). For paragraph leaves this
   * collapses to a plain single-id toggle.
   *
   * If every id in the subtree is already in the set → uncheck them all.
   * Otherwise (none or partial) → check them all. This makes
   * "click on All document" select everything for free.
   */
  const toggleSubtree = (node: HierarchyNode) => {
    const ids = collectSubtreeIds(node);
    if (ids.length === 0) return;
    setPickedNodeIds((prev) => {
      const next = new Set(prev);
      const allChecked = ids.every((id) => next.has(id));
      if (allChecked) {
        ids.forEach((id) => next.delete(id));
      } else {
        ids.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const runGeneration = async () => {
    if (pickedNodeIds.size === 0) {
      setError('Pick at least one section or paragraph to quiz on.');
      return;
    }
    setError(null);
    setPhase('generating');
    try {
      const r = await agentApi.generateQuiz(materialId, {
        node_ids: Array.from(pickedNodeIds),
        item_type: itemType,
        n,
        difficulty,
      });
      if (!r.data.quiz?.items || r.data.quiz.items.length === 0) {
        const warns = r.data.quiz?.metadata?.warnings?.join(' | ') || 'no items produced';
        setError(`Quiz returned 0 items: ${warns}`);
        setPhase('error');
        return;
      }
      setQuiz(r.data.quiz);
      setQuizArtifactId(r.data.artifact_id);
      setPhase('playing');
    } catch (e: any) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message || 'Quiz generation failed';
      const prefix =
        status === 429 ? '⏱ ' :
        status === 422 ? '📝 ' :
        status === 400 ? '📏 ' : '⚠ ';
      setError(prefix + detail);
      setPhase('error');
    }
  };

  return (
    <div
      onClick={onClose}
      // Block wheel / touch scroll from chaining to whatever sits below the
      // backdrop (the reader's own scroll container, the body, …). The card
      // inside has its own overflow so users can still scroll the form.
      onWheel={(e) => e.preventDefault()}
      onTouchMove={(e) => e.preventDefault()}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        // Stop our backdrop's onWheel preventDefault from killing scroll
        // INSIDE the modal — the card needs its own scroll to work.
        onWheel={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
        style={{
          background: 'white', borderRadius: 12,
          width: 'min(720px, 92vw)', maxHeight: '88vh',
          overflowY: 'auto',
          // Contain scroll-chain so reaching the top/bottom of the card
          // doesn't bleed into any scrollable ancestor.
          overscrollBehavior: 'contain',
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
          padding: 24, boxSizing: 'border-box',
          display: 'flex', flexDirection: 'column', gap: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Test my knowledges</h2>
          <button
            onClick={onClose}
            style={{
              border: 'none', background: 'transparent', fontSize: 22,
              cursor: 'pointer', color: '#888', lineHeight: 1,
            }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {phase === 'form' && (
          <FormPhase
            entries={pickerEntries}
            pickedNodeIds={pickedNodeIds}
            toggleSubtree={toggleSubtree}
            itemType={itemType} setItemType={setItemType}
            n={n} setN={setN}
            difficulty={difficulty} setDifficulty={setDifficulty}
            onGenerate={runGeneration}
            disabled={pickedNodeIds.size === 0}
          />
        )}

        {phase === 'generating' && (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <div style={{ fontSize: 28 }}>⏳</div>
            <div style={{ marginTop: 8, color: '#555' }}>Generating items…</div>
            <div style={{ marginTop: 4, color: '#999', fontSize: 12 }}>
              The LLM is reading the section and producing {n} item(s).
            </div>
          </div>
        )}

        {phase === 'error' && (
          <div>
            <div style={{
              padding: 12, background: '#fdebee', borderLeft: '4px solid #c0392b',
              borderRadius: 4, fontSize: 14, color: '#922', whiteSpace: 'pre-wrap',
            }}>
              {error}
            </div>
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={onClose} style={btn('#aaa')}>Close</button>
              <button onClick={() => setPhase('form')} style={btn('#3498db')}>Back to form</button>
            </div>
          </div>
        )}

        {phase === 'playing' && quiz && quizArtifactId !== null && (
          <QuizPlayer
            materialId={materialId}
            quizId={quizArtifactId}
            items={quiz.items}
          />
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────

/**
 * One row of the scope picker. Displays a tri-state checkbox:
 *   - checked       → every node in this subtree is selected
 *   - indeterminate → some, but not all, nodes in this subtree are selected
 *   - unchecked     → nothing in this subtree is selected
 *
 * Indeterminate is a DOM-only property (no HTML attribute), so we set it
 * imperatively via a ref. `onToggle` cascades the click to the whole subtree.
 */
function PickerRow({
  entry, picked, onToggle,
}: {
  entry: PickerEntry;
  picked: Set<string>;
  onToggle: () => void;
}) {
  // Compute subtree-wide check state.
  const subtreeIds = useMemo(() => collectSubtreeIds(entry.node), [entry.node]);
  const total = subtreeIds.length;
  const inSet = subtreeIds.reduce((acc, id) => acc + (picked.has(id) ? 1 : 0), 0);
  const checked = total > 0 && inSet === total;
  const indeterminate = inSet > 0 && inSet < total;

  // Indent proportionally to depth so the hierarchy is visible at a glance.
  const pad = entry.isRoot ? 0 : Math.max(0, entry.depth - 1) * 14;

  return (
    <label
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '3px 4px', paddingLeft: 4 + pad,
        borderRadius: 3, cursor: 'pointer',
        background: checked ? '#e8f4fd' : indeterminate ? '#f3f8fc' : 'transparent',
        fontWeight: entry.isRoot ? 700 : (entry.node.kind !== 'paragraph' ? 600 : 400),
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        ref={(el) => { if (el) el.indeterminate = indeterminate; }}
        onChange={onToggle}
        style={{ flexShrink: 0 }}
      />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {entry.isRoot ? '📄 ' : ''}{entry.label.replace(/^\s+/, '')}
      </span>
    </label>
  );
}


function FormPhase(props: {
  entries: PickerEntry[];
  pickedNodeIds: Set<string>;
  toggleSubtree: (node: HierarchyNode) => void;
  itemType: ItemTypeCode; setItemType: (v: ItemTypeCode) => void;
  n: number; setN: (v: number) => void;
  difficulty: Difficulty; setDifficulty: (v: Difficulty) => void;
  onGenerate: () => void;
  disabled: boolean;
}) {
  const {
    entries, pickedNodeIds, toggleSubtree,
    itemType, setItemType, n, setN, difficulty, setDifficulty, onGenerate, disabled,
  } = props;
  return (
    <>
      <div>
        <label style={lbl}>
          Scope <span style={{ color: '#789', fontWeight: 400 }}>· tick a section to include everything below it</span>
        </label>
        <div style={{
          maxHeight: 240, overflowY: 'auto',
          border: '1px solid #ccc', borderRadius: 4, padding: 8,
          background: '#fafbfc', fontSize: 13,
        }}>
          {entries.length === 0 && (
            <div style={{ color: '#789', fontStyle: 'italic' }}>(no index loaded)</div>
          )}
          {entries.map((e) => (
            <PickerRow
              key={e.node.node_id}
              entry={e}
              picked={pickedNodeIds}
              onToggle={() => toggleSubtree(e.node)}
            />
          ))}
        </div>
        <div style={{ fontSize: 11, color: '#789', marginTop: 4 }}>
          Cascading: ticking a section auto-selects every paragraph below it.
          A square inside the box ▣ means partial selection within that subtree.
        </div>
      </div>
      <div>
        <label style={lbl}>Type</label>
        <select value={itemType} onChange={(e) => setItemType(e.target.value as ItemTypeCode)} style={ctrl}>
          <option value="qa">Open question</option>
          <option value="mcq">Multiple choice</option>
          <option value="f">Flashcard</option>
        </select>
      </div>
      <div>
        <label style={lbl}>Difficulty</label>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)} style={ctrl}>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
      </div>
      <div>
        <label style={lbl}>Number of items: <b>{n}</b></label>
        <input type="range" min={1} max={10} value={n}
               onChange={(e) => setN(parseInt(e.target.value))} style={{ width: '100%' }} />
      </div>
      <button onClick={onGenerate} disabled={disabled}
              style={{ ...btn('#27ae60'), padding: '12px 20px', fontSize: 15 }}>
        Generate ({pickedNodeIds.size} selected)
      </button>
    </>
  );
}

const lbl: React.CSSProperties = {
  display: 'block', fontSize: 13, marginBottom: 4, color: '#444',
};
const ctrl: React.CSSProperties = {
  width: '100%', padding: 8, fontSize: 14, borderRadius: 4, border: '1px solid #ccc',
};
const btn = (bg: string): React.CSSProperties => ({
  padding: '8px 16px', background: bg, color: 'white',
  border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600,
});
