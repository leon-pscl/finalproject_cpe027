import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  formatTimestamp,
  generateNotes,
  generateTranscript,
  inspectAudio,
  validateAudio,
  type TranscriptSegment,
} from '../services/mock';
import { RecordingContext, type ChatMessage, type PlayerState, type Stage, type Tab } from './context';

const SPEEDS = [1, 1.25, 1.5, 2, 0.75];
const TRANSCRIBE_MS = 3000;
const NOTES_MS = 2500;
const NOTES_REQUEST = 'Generate structured study notes with key definitions.';

const idlePlayer: PlayerState = { currentTime: 0, duration: 0, playing: false, speed: 1 };

/** Demo-only: picks the transcript segment sharing the most words with the question. */
function mockAnswer(question: string, transcript: TranscriptSegment[]): string {
  if (transcript.length === 0) return 'Upload a recording first, then ask me about it.';
  if (/notes|summary|summari[sz]e|definitions?/i.test(question)) {
    const sections = generateNotes(transcript).map((note) => note.section);
    return `Study notes are ready: ${sections.join(', ')}.`;
  }
  const words = question.toLowerCase().match(/[a-z]{4,}/g) ?? [];
  let best = transcript[0];
  let bestScore = -1;
  for (const segment of transcript) {
    const score = words.filter((word) => segment.text.toLowerCase().includes(word)).length;
    if (score > bestScore) {
      best = segment;
      bestScore = score;
    }
  }
  return `[${formatTimestamp(best.start)}] ${best.text}`;
}

export function RecordingProvider({ children }: { children: ReactNode }) {
  const [stage, setStage] = useState<Stage>('idle');
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [player, setPlayer] = useState<PlayerState>(idlePlayer);
  const [tab, setTab] = useState<Tab>('chat');

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const idRef = useRef(0);
  const fallbackDuration = useRef(0);

  const addMessage = useCallback((from: ChatMessage['from'], text: string) => {
    idRef.current += 1;
    const id = idRef.current;
    setMessages((current) => [...current, { id, from, text }]);
  }, []);

  const teardownAudio = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (urlRef.current) {
      try {
        URL.revokeObjectURL(urlRef.current);
      } catch {
        /* ignore */
      }
      urlRef.current = null;
    }
  }, []);

  useEffect(() => teardownAudio, [teardownAudio]);

  const start = useCallback(
    (file: File) => {
      const validation = validateAudio(file);
      if (!validation.isValid) {
        setFileError(validation.message ?? 'Unsupported file.');
        return;
      }
      teardownAudio();
      setFileError(null);

      const segments = generateTranscript();
      const info = inspectAudio(file);
      fallbackDuration.current = Math.max(info?.estimatedDuration ?? 0, segments[segments.length - 1].start + 30);

      try {
        const url = URL.createObjectURL(file);
        urlRef.current = url;
        const audio = new Audio(url);
        audio.preload = 'metadata';
        audio.addEventListener('timeupdate', () => setPlayer((p) => ({ ...p, currentTime: audio.currentTime })));
        audio.addEventListener('loadedmetadata', () => {
          if (Number.isFinite(audio.duration)) setPlayer((p) => ({ ...p, duration: audio.duration }));
        });
        audio.addEventListener('play', () => setPlayer((p) => ({ ...p, playing: true })));
        audio.addEventListener('pause', () => setPlayer((p) => ({ ...p, playing: false })));
        audio.addEventListener('ended', () => setPlayer((p) => ({ ...p, playing: false })));
        audio.addEventListener('error', () => setPlayer((p) => ({ ...p, playing: false })));
        audioRef.current = audio;
      } catch {
        audioRef.current = null; /* no audio support: UI still works */
      }

      setFileName(file.name);
      setTranscript(segments);
      setMessages([]);
      setPlayer({ ...idlePlayer, duration: fallbackDuration.current });
      setTab('chat');
      setProgress(0);
      setStage('transcribing');
    },
    [teardownAudio],
  );

  const reset = useCallback(() => {
    teardownAudio();
    setStage('idle');
    setProgress(0);
    setFileName(null);
    setFileError(null);
    setTranscript([]);
    setMessages([]);
    setPlayer(idlePlayer);
    setTab('chat');
  }, [teardownAudio]);

  // Simulated pipeline: transcribing -> generating notes -> ready.
  useEffect(() => {
    if (stage !== 'transcribing' && stage !== 'generatingNotes') return;
    const total = stage === 'transcribing' ? TRANSCRIBE_MS : NOTES_MS;
    const startedAt = Date.now();
    setProgress(0);
    const timer = window.setInterval(() => {
      const pct = Math.min(100, ((Date.now() - startedAt) / total) * 100);
      setProgress(pct);
      if (pct < 100) return;
      window.clearInterval(timer);
      if (stage === 'transcribing') {
        addMessage('you', NOTES_REQUEST);
        setStage('generatingNotes');
      } else {
        const sections = generateNotes([]).map((note) => note.section);
        addMessage('assistant', `Notes ready (${sections.length} sections). Ask me about any part of the lecture.`);
        setStage('ready');
      }
    }, 100);
    return () => window.clearInterval(timer);
  }, [stage, addMessage]);

  const ask = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question) return;
      addMessage('you', question);
      addMessage('assistant', mockAnswer(question, transcript));
    },
    [addMessage, transcript],
  );

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const result = audio.play() as Promise<void> | undefined;
    result?.catch(() => setPlayer((p) => ({ ...p, playing: false })));
  }, []);

  const pause = useCallback(() => audioRef.current?.pause(), []);

  const cycleSpeed = useCallback(() => {
    setPlayer((p) => {
      const next = SPEEDS[(SPEEDS.indexOf(p.speed) + 1) % SPEEDS.length];
      if (audioRef.current) audioRef.current.playbackRate = next;
      return { ...p, speed: next };
    });
  }, []);

  const seek = useCallback((seconds: number) => {
    if (audioRef.current) {
      try {
        audioRef.current.currentTime = seconds;
      } catch {
        /* metadata not loaded yet */
      }
    }
    setPlayer((p) => ({ ...p, currentTime: seconds }));
  }, []);

  const value = useMemo(
    () => ({ stage, progress, fileName, fileError, transcript, messages, player, tab, setTab, start, reset, ask, play, pause, cycleSpeed, seek }),
    [stage, progress, fileName, fileError, transcript, messages, player, tab, start, reset, ask, play, pause, cycleSpeed, seek],
  );

  return <RecordingContext.Provider value={value}>{children}</RecordingContext.Provider>;
}
