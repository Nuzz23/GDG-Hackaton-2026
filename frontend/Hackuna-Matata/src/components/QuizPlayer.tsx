import { useState } from 'react';
import { agentApi } from '@/services/api';
import type {
  AssessmentItemAny, FlashcardItem, MCQItem, OpenQuestionItem,
  TraceEvent,
} from '@/types/apiTypes';
import { AudioRecorder } from './AudioRecorder';

interface QuizPlayerProps {
  materialId: number;
  quizId: number;
  items: AssessmentItemAny[];
}

/**
 * Plays a generated quiz one item at a time. For each item: collects the
 * student's response, calls the eval endpoint, displays the conversational
 * intervention message + (when available) the source-redirect pointer.
 *
 * The student NEVER sees the rubric values. They see only:
 *   - the intervention message (LLM-generated, in the source language)
 *   - the source pointer when applicable (locator_summary)
 *
 * This mirrors the brief's "rubric is the agent's compass, not the student's grade".
 */
export function QuizPlayer({ materialId, quizId, items }: QuizPlayerProps) {
  const [idx, setIdx] = useState(0);
  const [textAnswer, setTextAnswer] = useState('');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [trace, setTrace] = useState<TraceEvent | null>(null);
  const [allTraces, setAllTraces] = useState<TraceEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(`session_${Date.now()}`);

  if (idx >= items.length) {
    return <SessionSummary total={items.length} traces={allTraces} />;
  }

  const current = items[idx];

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const r = await agentApi.evaluateResponse(materialId, quizId, {
        itemIndex: idx,
        responseText: audioBlob ? undefined : textAnswer,
        responseAudio: audioBlob ?? undefined,
        sessionId,
      });
      setTrace(r.data.trace);
      setAllTraces((prev) => [...prev, r.data.trace]);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Evaluation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const next = () => {
    setIdx(idx + 1);
    setTextAnswer('');
    setAudioBlob(null);
    setTrace(null);
    setError(null);
  };

  return (
    <div style={{
      padding: 16, border: '1px solid #ddd', borderRadius: 8, background: 'white',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: '#666' }}>
          Item {idx + 1} / {items.length}
          {' · '}
          difficulty: <b>{current.difficulty}</b>
        </span>
        <span style={{ fontSize: 12, color: '#666', fontFamily: 'monospace' }}>
          {current.item_type}
        </span>
      </div>

      <ItemBody item={current} />

      {/* Response area (hidden once we have a trace) */}
      {!trace && (
        <ResponseInput
          itemType={current.item_type}
          textAnswer={textAnswer}
          setTextAnswer={setTextAnswer}
          audioBlob={audioBlob}
          setAudioBlob={setAudioBlob}
          submitting={submitting}
        />
      )}

      {!trace && (
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <button
            onClick={submit}
            disabled={submitting || (!textAnswer && !audioBlob)}
            style={{
              padding: '10px 20px', background: '#27ae60', color: 'white',
              border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 'bold',
            }}
          >
            {submitting ? 'Evaluating…' : 'Submit answer'}
          </button>
        </div>
      )}

      {error && (
        <div style={{ marginTop: 12, color: '#c0392b', fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {/* Intervention display */}
      {trace && (
        <InterventionDisplay
          trace={trace}
          onNext={next}
          isLast={idx === items.length - 1}
        />
      )}
    </div>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────

function ItemBody({ item }: { item: AssessmentItemAny }) {
  if (item.item_type === 'f') {
    const f = item as FlashcardItem;
    return (
      <div>
        <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>FRONT (flashcard)</div>
        <div style={{ fontSize: 18, fontWeight: 500 }}>{f.front}</div>
      </div>
    );
  }
  if (item.item_type === 'mcq') {
    const m = item as MCQItem;
    return (
      <div>
        <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>MCQ</div>
        <div style={{ fontSize: 18, fontWeight: 500, marginBottom: 12 }}>{m.question}</div>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {m.options.map((opt, i) => (
            <li key={i} style={{
              padding: '6px 10px', marginBottom: 4,
              background: '#f8f9fa', borderRadius: 4, fontSize: 14,
            }}>
              <b style={{ color: '#666', marginRight: 8 }}>{String.fromCharCode(65 + i)}.</b>
              {opt}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  // qa
  const q = item as OpenQuestionItem;
  return (
    <div>
      <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>OPEN QUESTION</div>
      <div style={{ fontSize: 18, fontWeight: 500 }}>{q.question}</div>
    </div>
  );
}

function ResponseInput(props: {
  itemType: string;
  textAnswer: string;
  setTextAnswer: (s: string) => void;
  audioBlob: Blob | null;
  setAudioBlob: (b: Blob | null) => void;
  submitting: boolean;
}) {
  const { itemType, textAnswer, setTextAnswer, setAudioBlob, submitting } = props;

  if (itemType === 'mcq') {
    // For MCQ we accept letter or number
    return (
      <div style={{ marginTop: 16 }}>
        <input
          type="text"
          value={textAnswer}
          onChange={(e) => setTextAnswer(e.target.value)}
          placeholder="A / B / C / D   or   1 / 2 / 3 / 4"
          disabled={submitting}
          style={{
            width: '100%', padding: 10, fontSize: 16,
            border: '1px solid #ccc', borderRadius: 4,
          }}
        />
      </div>
    );
  }

  // Flashcard or open question — text + audio (audio only useful for qa really)
  return (
    <div style={{ marginTop: 16 }}>
      <textarea
        value={textAnswer}
        onChange={(e) => setTextAnswer(e.target.value)}
        placeholder="Type your answer here…"
        rows={4}
        disabled={submitting}
        style={{
          width: '100%', padding: 10, fontSize: 14, fontFamily: 'inherit',
          border: '1px solid #ccc', borderRadius: 4, resize: 'vertical',
        }}
      />
      {itemType === 'qa' && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
            …or answer by voice (recommended for open questions):
          </div>
          <AudioRecorder onRecordingComplete={setAudioBlob} disabled={submitting} />
        </div>
      )}
    </div>
  );
}

function InterventionDisplay({
  trace, onNext, isLast,
}: { trace: TraceEvent; onNext: () => void; isLast: boolean }) {
  const { intervention } = trace;
  const { kind, student_message, source_redirect } = intervention;

  const palette: Record<string, { bg: string; border: string; emoji: string }> = {
    advance:            { bg: '#e8f8e8', border: '#27ae60', emoji: '✓' },
    hint_plus_redirect: { bg: '#fff8e1', border: '#f39c12', emoji: '💡' },
    redirect_only:      { bg: '#fff8e1', border: '#f39c12', emoji: '📖' },
    modality_switch:    { bg: '#e8f4fd', border: '#3498db', emoji: '🔄' },
    full_redirect:      { bg: '#fdebee', border: '#c0392b', emoji: '↩' },
  };
  const p = palette[kind] || palette.advance;

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{
        padding: 16, background: p.bg, borderLeft: `4px solid ${p.border}`,
        borderRadius: 4,
      }}>
        <div style={{ fontSize: 24, marginBottom: 6 }}>{p.emoji}</div>
        <div style={{ fontSize: 16, lineHeight: 1.5 }}>{student_message}</div>
        {source_redirect && source_redirect.excerpt && (
          <details style={{ marginTop: 12, fontSize: 13, color: '#555' }}>
            <summary style={{ cursor: 'pointer' }}>
              📍 {source_redirect.locator_summary}
            </summary>
            <blockquote style={{
              margin: '8px 0 0 0', padding: 10, background: 'rgba(0,0,0,0.04)',
              borderLeft: '2px solid #999', fontStyle: 'italic', whiteSpace: 'pre-wrap',
            }}>
              {source_redirect.excerpt}
            </blockquote>
          </details>
        )}
      </div>
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={onNext}
          style={{
            padding: '10px 20px', background: '#3498db', color: 'white',
            border: 'none', borderRadius: 4, cursor: 'pointer',
          }}
        >
          {isLast ? 'Finish session' : 'Next item →'}
        </button>
      </div>
    </div>
  );
}

/**
 * End-of-session screen — short, English, 3-metric recap aggregated from
 * the open-question judgments collected during the session.
 *
 * Closed-form items (flashcard / mcq) don't carry the 3-D rubric, so we
 * report them separately as a simple correct/total count.
 */
function SessionSummary({ total, traces }: { total: number; traces: TraceEvent[] }) {
  // Split judgments by type — the 3-metric recap only applies to open ones.
  const openJudgments = traces
    .map((t) => t.judgment)
    .filter((j): j is Extract<TraceEvent['judgment'], { judgment_type: 'open' }> => j.judgment_type === 'open');
  const closedJudgments = traces
    .map((t) => t.judgment)
    .filter((j): j is Extract<TraceEvent['judgment'], { judgment_type: 'closed' }> => j.judgment_type === 'closed');

  // Numerical encoding so we can average across attempts. Same scale per
  // metric: 2 = best, 0 = worst. The label thresholds below mirror what a
  // teacher would intuitively call good / partial / weak.
  const score = {
    completezza: { alta: 2, parziale: 1, assente: 0 } as const,
    correttezza: { corretta: 2, parzialmente_corretta: 1, errata: 0 } as const,
    elaborazione: { rielaborata: 2, riportata: 1, non_valutabile: 1 } as const,
  };

  const labelFor = (avg: number): 'good' | 'partial' | 'weak' =>
    avg >= 1.5 ? 'good' : avg >= 0.75 ? 'partial' : 'weak';

  const avg = (xs: number[]) =>
    xs.length === 0 ? null : xs.reduce((a, b) => a + b, 0) / xs.length;

  const completenessAvg = avg(openJudgments.map((j) => score.completezza[j.completezza]));
  const correctnessAvg = avg(openJudgments.map((j) => score.correttezza[j.correttezza]));
  const reformulationAvg = avg(openJudgments.map((j) => score.elaborazione[j.elaborazione]));

  const closedCorrect = closedJudgments.filter((j) => j.correct).length;

  return (
    <div style={{ padding: 20, background: '#f8f9fa', borderRadius: 8 }}>
      <h3 style={{ marginTop: 0 }}>🎉 Session complete</h3>
      <p style={{ marginTop: 0, color: '#456' }}>
        You worked through all {total} items.
      </p>

      {openJudgments.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: '#789', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
            Open questions ({openJudgments.length})
          </div>
          <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
            <MetricLine label="Completeness"  value={completenessAvg}  labelFor={labelFor} />
            <MetricLine label="Correctness"   value={correctnessAvg}   labelFor={labelFor} />
            <MetricLine label="Reformulation" value={reformulationAvg} labelFor={labelFor} />
          </ul>
        </div>
      )}

      {closedJudgments.length > 0 && (
        <p style={{ marginTop: 14, color: '#234' }}>
          Closed items: <b>{closedCorrect} / {closedJudgments.length}</b> correct.
        </p>
      )}

      {traces.length === 0 && (
        <p style={{ color: '#789', fontStyle: 'italic' }}>
          No answers were submitted during this session.
        </p>
      )}
    </div>
  );
}

function MetricLine({
  label, value, labelFor,
}: {
  label: string;
  value: number | null;
  labelFor: (v: number) => 'good' | 'partial' | 'weak';
}) {
  if (value === null) return null;
  const verdict = labelFor(value);
  const color = verdict === 'good' ? '#27ae60' : verdict === 'partial' ? '#f39c12' : '#c0392b';
  return (
    <li>
      <b>{label}:</b>{' '}
      <span style={{ color, fontWeight: 600 }}>{verdict}</span>
    </li>
  );
}
