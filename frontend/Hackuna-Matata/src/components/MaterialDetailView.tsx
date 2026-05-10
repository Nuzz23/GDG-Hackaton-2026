import { useEffect, useState } from 'react';
import { agentApi } from '@/services/api';
import type {
  HierarchyNode, IndexOutput, QuizOutput, ItemTypeCode, Difficulty,
} from '@/types/apiTypes';
import { IndexTree } from './IndexTree';
import { QuizPlayer } from './QuizPlayer';
import { nodeTitle } from '@/utils/nodeTitle';

interface MaterialDetailViewProps {
  groupId: number;
  materialId: number;
  materialName: string;
  onBack: () => void;
}

type Phase = 'idle' | 'indexing' | 'index_ready' | 'generating' | 'playing';

/**
 * The full AI flow for a single material:
 *   1. (idle)         Show "Index this material" button
 *   2. (indexing)     Spinner while processing_agent runs
 *   3. (index_ready)  Show IndexTree; user picks a node
 *   4. (generating)   Form (type/n/difficulty) → spinner while quiz_creation_agent runs
 *   5. (playing)      QuizPlayer takes over
 */
export function MaterialDetailView(props: MaterialDetailViewProps) {
  const { groupId, materialId, materialName, onBack } = props;

  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<IndexOutput | null>(null);
  const [selectedNode, setSelectedNode] = useState<HierarchyNode | null>(null);
  const [quiz, setQuiz] = useState<QuizOutput | null>(null);
  const [quizArtifactId, setQuizArtifactId] = useState<number | null>(null);

  // Form for quiz generation
  const [itemType, setItemType] = useState<ItemTypeCode>('qa');
  const [n, setN] = useState<number>(3);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');

  // On mount, try to load an existing index for this material
  useEffect(() => {
    (async () => {
      try {
        const r = await agentApi.getLatestIndex(materialId);
        setIndex(r.data.index);
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
      setIndex(r.data.index);
      setPhase('index_ready');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Indexing failed');
      setPhase('idle');
    }
  };

  const runQuizGeneration = async () => {
    if (!selectedNode) return;
    setError(null);
    setPhase('generating');
    try {
      const r = await agentApi.generateQuiz(materialId, {
        node_id: selectedNode.node_id,
        item_type: itemType,
        n,
        difficulty,
      });
      setQuiz(r.data.quiz);
      setQuizArtifactId(r.data.artifact_id);
      setPhase('playing');
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Quiz generation failed');
      setPhase('index_ready');
    }
  };

  const restart = () => {
    setQuiz(null);
    setQuizArtifactId(null);
    setSelectedNode(null);
    setPhase('index_ready');
  };

  return (
    <div style={{
      width: '100%', height: '100%', padding: 24, overflowY: 'auto',
      boxSizing: 'border-box',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 20,
      }}>
        <h2 style={{ margin: 0 }}>📚 {materialName}</h2>
        <button onClick={onBack} style={{ padding: '6px 12px', cursor: 'pointer' }}>
          ← Back
        </button>
      </div>

      {error && (
        <div style={{
          padding: 12, background: '#fdebee', borderLeft: '4px solid #c0392b',
          marginBottom: 16, fontSize: 14, color: '#922',
        }}>
          ⚠ {error}
        </div>
      )}

      {/* PHASE: idle ────────────────────────────────── */}
      {phase === 'idle' && (
        <div style={{ textAlign: 'center', padding: 40 }}>
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

      {/* PHASE: indexing ─────────────────────────────── */}
      {phase === 'indexing' && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <p>Indexing in progress…</p>
          <p style={{ fontSize: 12, color: '#888' }}>
            processing_agent is parsing the file and extracting the structure.
          </p>
        </div>
      )}

      {/* PHASE: index_ready or generating ────────────── */}
      {(phase === 'index_ready' || phase === 'generating') && index && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Left: Index tree */}
          <div style={{
            border: '1px solid #ddd', borderRadius: 8, padding: 16,
            background: 'white', maxHeight: '70vh', overflowY: 'auto',
          }}>
            <h3 style={{ marginTop: 0 }}>Index</h3>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>
              {index.source.filename} · {index.source.language} ·{' '}
              {Object.entries(index.source.size_metric).map(([k, v]) => `${v} ${k}`).join(', ')}
            </div>
            <IndexTree
              node={index.tree}
              selectedNodeId={selectedNode?.node_id || null}
              onSelect={(n) => setSelectedNode(n)}
            />
          </div>

          {/* Right: Quiz generation form */}
          <div style={{
            border: '1px solid #ddd', borderRadius: 8, padding: 16, background: 'white',
          }}>
            <h3 style={{ marginTop: 0 }}>Generate quiz</h3>
            {!selectedNode ? (
              <p style={{ color: '#888', fontStyle: 'italic' }}>
                Pick a node from the index on the left.
              </p>
            ) : (
              <>
                <div style={{ marginBottom: 16, padding: 10, background: '#e8f4fd', borderRadius: 4 }}>
                  <div style={{ fontSize: 12, color: '#555' }}>Selected:</div>
                  <div style={{ fontWeight: 'bold' }}>
                    {nodeTitle(selectedNode, 80)}
                  </div>
                  <div style={{ fontSize: 11, color: '#888', textTransform: 'capitalize' }}>
                    {selectedNode.kind}
                  </div>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 4 }}>Type</label>
                  <select
                    value={itemType}
                    onChange={(e) => setItemType(e.target.value as ItemTypeCode)}
                    style={{ width: '100%', padding: 8, fontSize: 14 }}
                  >
                    <option value="qa">Open question</option>
                    <option value="mcq">Multiple choice</option>
                    <option value="f">Flashcard</option>
                  </select>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 4 }}>Difficulty</label>
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value as Difficulty)}
                    style={{ width: '100%', padding: 8, fontSize: 14 }}
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: 13, marginBottom: 4 }}>
                    Number of items: <b>{n}</b>
                  </label>
                  <input
                    type="range" min={1} max={10} value={n}
                    onChange={(e) => setN(parseInt(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>

                <button
                  onClick={runQuizGeneration}
                  disabled={phase === 'generating'}
                  style={{
                    padding: '10px 20px', fontSize: 15, background: '#27ae60',
                    color: 'white', border: 'none', borderRadius: 4,
                    cursor: phase === 'generating' ? 'wait' : 'pointer',
                    width: '100%',
                  }}
                >
                  {phase === 'generating' ? '⏳ Generating…' : 'Generate'}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* PHASE: playing ──────────────────────────────── */}
      {phase === 'playing' && quiz && quizArtifactId !== null && (
        <div>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 13, color: '#666' }}>
              Quiz on: <b>{selectedNode ? nodeTitle(selectedNode, 50) : '—'}</b> ·{' '}
              {quiz.n_produced} {quiz.item_type} · {quiz.difficulty}
            </span>
            <button onClick={restart} style={{ padding: '4px 10px', cursor: 'pointer' }}>
              New quiz
            </button>
          </div>
          <QuizPlayer
            materialId={materialId}
            quizId={quizArtifactId}
            items={quiz.items}
          />
        </div>
      )}
    </div>
  );
}
