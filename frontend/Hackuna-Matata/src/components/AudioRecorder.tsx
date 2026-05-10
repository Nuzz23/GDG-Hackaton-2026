import { useEffect, useRef, useState } from 'react';

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  disabled?: boolean;
}

/**
 * Browser-side audio recorder using the MediaRecorder API.
 *
 * Records to whatever Opus/WebM format the browser provides (Whisper handles
 * it via ffmpeg on the backend). Shows a record/stop button + a live timer.
 * On stop, calls `onRecordingComplete` with the resulting Blob.
 */
export function AudioRecorder({ onRecordingComplete, disabled }: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [hasRecording, setHasRecording] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => () => {
    // Cleanup on unmount
    if (timerRef.current) window.clearInterval(timerRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
  }, []);

  const start = async () => {
    setError(null);
    chunksRef.current = [];
    setHasRecording(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        setHasRecording(true);
        onRecordingComplete(blob);
        // Stop tracks to release the mic indicator
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      };

      recorder.start();
      setIsRecording(true);
      setElapsed(0);
      const startTs = Date.now();
      timerRef.current = window.setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTs) / 1000));
      }, 200);
    } catch (e: any) {
      setError(e?.message || 'Could not start recording. Microphone permission denied?');
    }
  };

  const stop = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
  };

  const fmt = (s: number) => {
    const mm = Math.floor(s / 60).toString().padStart(2, '0');
    const ss = (s % 60).toString().padStart(2, '0');
    return `${mm}:${ss}`;
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {!isRecording ? (
        <button
          type="button"
          onClick={start}
          disabled={disabled}
          style={{
            padding: '8px 16px',
            background: '#c0392b',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          ● {hasRecording ? 'Re-record' : 'Record'}
        </button>
      ) : (
        <button
          type="button"
          onClick={stop}
          style={{
            padding: '8px 16px',
            background: '#2c3e50',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer',
          }}
        >
          ■ Stop ({fmt(elapsed)})
        </button>
      )}
      {hasRecording && !isRecording && (
        <span style={{ color: '#27ae60', fontSize: 14 }}>
          ✓ Recorded {fmt(elapsed)}
        </span>
      )}
      {error && <span style={{ color: '#c0392b', fontSize: 13 }}>{error}</span>}
    </div>
  );
}
