import { useEffect, useState } from 'react';
import { agentApi } from '@/services/api';
import type {
  Difficulty, HierarchyNode, ItemTypeCode, QuizOutput,
} from '@/types/apiTypes';
import { QuizPlayer } from './QuizPlayer';
import { nodeTitle } from '@/utils/nodeTitle';

interface QuizModalProps {
  isOpen: boolean;
  onClose: () => void;
  materialId: number;
  /** The node the quiz will be generated on. The reader feeds the
   *  currently-visible chapter/section here. */
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
export function QuizModal({ isOpen, onClose, materialId, targetNode }: QuizModalProps) {
  const [phase, setPhase] = useState<Phase>('form');
  const [error, setError] = useState<string | null>(null);
  const [quiz, setQuiz] = useState<QuizOutput | null>(null);
  const [quizArtifactId, setQuizArtifactId] = useState<number | null>(null);

  const [itemType, setItemType] = useState<ItemTypeCode>('qa');
  const [n, setN] = useState(3);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');

  // Reset to form whenever the modal is reopened with a (possibly new)
  // target node — we don't want stale quiz state lingering.
  useEffect(() => {
    if (isOpen) {
      setPhase('form');
      setError(null);
      setQuiz(null);
      setQuizArtifactId(null);
    }
  }, [isOpen, targetNode?.node_id]);

  if (!isOpen) return null;

  const runGeneration = async () => {
    if (!targetNode) {
      setError('No target node selected.');
      return;
    }
    setError(null);
    setPhase('generating');
    try {
      const r = await agentApi.generateQuiz(materialId, {
        node_id: targetNode.node_id,
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
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'white', borderRadius: 12,
          width: 'min(720px, 92vw)', maxHeight: '88vh',
          overflowY: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
          padding: 24, boxSizing: 'border-box',
          display: 'flex', flexDirection: 'column', gap: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Mettimi alla prova</h2>
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

        {/* Target indicator — always visible */}
        {targetNode && (
          <div style={{
            padding: 10, background: '#eef5fc', borderRadius: 6,
            fontSize: 13, color: '#356',
          }}>
            <div style={{ fontSize: 11, color: '#789' }}>Quiz on</div>
            <div style={{ fontWeight: 600 }}>{nodeTitle(targetNode, 100)}</div>
          </div>
        )}

        {phase === 'form' && (
          <FormPhase
            itemType={itemType} setItemType={setItemType}
            n={n} setN={setN}
            difficulty={difficulty} setDifficulty={setDifficulty}
            onGenerate={runGeneration}
            disabled={!targetNode}
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

function FormPhase(props: {
  itemType: ItemTypeCode; setItemType: (v: ItemTypeCode) => void;
  n: number; setN: (v: number) => void;
  difficulty: Difficulty; setDifficulty: (v: Difficulty) => void;
  onGenerate: () => void;
  disabled: boolean;
}) {
  const { itemType, setItemType, n, setN, difficulty, setDifficulty, onGenerate, disabled } = props;
  return (
    <>
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
        Generate
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
