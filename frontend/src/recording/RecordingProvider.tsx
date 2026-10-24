import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useAuth } from '../auth/useAuth';
import {
  formatTimestamp,
  generateNotes,
  generateTranscript,
  inspectAudio,
  validateAudio,
  type TranscriptSegment,
} from '../services/mock';
import { deleteAudio, loadAudio, saveAudio } from './audioStore';
import { RecordingContext, type ChatMessage, type ChatSession, type PlayerState, type Stage, type Tab } from './context';
import { NOTES_REQUEST, stripExtension } from './format';

const SPEEDS = [1, 1.25, 1.5, 2, 0.75];
const TRANSCRIBE_MS = 3000;
const NOTES_MS = 2500;
const DEFAULT_TITLE = 'New note';

const idlePlayer: PlayerState = { currentTime: 0, duration: 0, playing: false, speed: 1 };

function emptyChat(): ChatSession {
  const now = Date.now();
  return {
    id: `chat-${now}-${Math.random().toString(36).slice(2, 7)}`,
    title: DEFAULT_TITLE,
    createdAt: now,
    updatedAt: now,
    stage: 'idle',
    fileName: null,
    duration: 0,
    transcript: [],
    messages: [],
  };
}

const isEmpty = (chat: ChatSession) => chat.stage === 'idle' && !chat.fileName && chat.messages.length === 0;
const isProcessing = (chat: ChatSession) => chat.stage === 'transcribing' || chat.stage === 'generatingNotes';

type Saved = { chats: ChatSession[]; activeId: string | null };

/** Reads this user's chats back from localStorage. Anything that was mid-processing on close becomes an empty note. */
function loadSaved(key: string): Saved {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return { chats: [], activeId: null };
    const parsed = JSON.parse(raw) as Partial<Saved>;
    const chats = (Array.isArray(parsed.chats) ? parsed.chats : [])
      .filter((chat): chat is ChatSession => !!chat && typeof chat.id === 'string' && Array.isArray(chat.messages))
      .map((chat) => {
        if (!isProcessing(chat)) return chat;
        void deleteAudio(chat.id);
        return { ...chat, stage: 'idle' as Stage, fileName: null, transcript: [], duration: 0 };
      });
    const activeId = chats.some((chat) => chat.id === parsed.activeId) ? (parsed.activeId as string) : null;
    return { chats, activeId };
  } catch {
    return { chats: [], activeId: null };
  }
}

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
  const { user } = useAuth();
  const storageKey = `lectureflow.chats.${user?.identifier ?? 'guest'}`;

  const [initial] = useState(() => loadSaved(storageKey));
  const [chats, setChats] = useState<ChatSession[]>(initial.chats);
  const [activeId, setActiveId] = useState<string | null>(initial.activeId);
  const [progressById, setProgressById] = useState<Record<string, number>>({});
  const [fileError, setFileError] = useState<string | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState>(idlePlayer);
  const [tab, setTab] = useState<Tab>('chat');

  const chatsRef = useRef(chats);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const blobsRef = useRef(new Map<string, Blob>());
  const timersRef = useRef(new Map<string, { stage: Stage; at: number }>());
  const msgRef = useRef(0);

  useEffect(() => {
    chatsRef.current = chats;
  });

  // Persist on every change so a refresh (or closing the tab) keeps the chats.
  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({ chats, activeId }));
    } catch {
      /* storage full or unavailable: chats last until reload */
    }
  }, [chats, activeId, storageKey]);

  const active = chats.find((chat) => chat.id === activeId) ?? null;
  const activeFileName = active?.fileName ?? null;

  const makeMessage = useCallback((from: ChatMessage['from'], text: string): ChatMessage => {
    msgRef.current += 1;
    return { id: Date.now() + msgRef.current, from, text };
  }, []);

  /* ---------- audio element lifecycle ---------- */
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

  const attachAudio = useCallback(
    (blob: Blob) => {
      teardownAudio();
      try {
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        const audio = new Audio(url);
        audio.preload = 'metadata';
        audio.addEventListener('timeupdate', () => setPlayerState((p) => ({ ...p, currentTime: audio.currentTime })));
        audio.addEventListener('loadedmetadata', () => {
          if (Number.isFinite(audio.duration)) setPlayerState((p) => ({ ...p, duration: audio.duration }));
        });
        audio.addEventListener('play', () => setPlayerState((p) => ({ ...p, playing: true })));
        audio.addEventListener('pause', () => setPlayerState((p) => ({ ...p, playing: false })));
        audio.addEventListener('ended', () => setPlayerState((p) => ({ ...p, playing: false })));
        audio.addEventListener('error', () => setPlayerState((p) => ({ ...p, playing: false })));
        audioRef.current = audio;
      } catch {
        audioRef.current = null; /* no audio support: UI still works */
      }
    },
    [teardownAudio],
  );

  // Load (or reload after a refresh) the audio for whichever chat is open.
  useEffect(() => {
    setPlayerState(idlePlayer);
    if (!activeId || !activeFileName) return;
    let cancelled = false;
    void (async () => {
      const blob = blobsRef.current.get(activeId) ?? (await loadAudio(activeId));
      if (!cancelled && blob) attachAudio(blob);
    })();
    return () => {
      cancelled = true;
      teardownAudio();
    };
  }, [activeId, activeFileName, attachAudio, teardownAudio]);

  /* ---------- simulated pipeline: runs for every chat that is processing, not just the open one ---------- */
  const processingCount = chats.filter(isProcessing).length;
  useEffect(() => {
    if (processingCount === 0) return;
    const timer = window.setInterval(() => {
      const now = Date.now();
      const updates: Record<string, number> = {};
      const finished: ChatSession[] = [];

      for (const chat of chatsRef.current) {
        if (!isProcessing(chat)) continue;
        let entry = timersRef.current.get(chat.id);
        if (!entry || entry.stage !== chat.stage) {
          entry = { stage: chat.stage, at: now };
          timersRef.current.set(chat.id, entry);
        }
        const total = chat.stage === 'transcribing' ? TRANSCRIBE_MS : NOTES_MS;
        const pct = Math.min(100, ((now - entry.at) / total) * 100);
        updates[chat.id] = pct >= 100 ? 0 : pct;
        if (pct >= 100) finished.push(chat);
      }

      setProgressById((current) => ({ ...current, ...updates }));

      for (const chat of finished) {
        const toNotes = chat.stage === 'transcribing';
        const message = toNotes
          ? makeMessage('you', NOTES_REQUEST)
          : makeMessage(
              'assistant',
              `Notes ready (${generateNotes([]).length} sections). Ask me about any part of the lecture.`,
            );
        setChats((current) =>
          current.map((item) =>
            item.id === chat.id && item.stage === chat.stage
              ? { ...item, stage: toNotes ? 'generatingNotes' : 'ready', messages: [...item.messages, message], updatedAt: now }
              : item,
          ),
        );
      }
    }, 100);
    return () => window.clearInterval(timer);
  }, [processingCount, makeMessage]);

  /* ---------- chat actions ---------- */
  const newNote = useCallback(() => {
    setTab('chat');
    setFileError(null);
    const current = chatsRef.current.find((chat) => chat.id === activeId);
    if (current && isEmpty(current)) return;
    const reusable = chatsRef.current.find(isEmpty);
    if (reusable) {
      setActiveId(reusable.id);
      return;
    }
    const chat = emptyChat();
    setChats((existing) => [...existing, chat]);
    setActiveId(chat.id);
  }, [activeId]);

  const selectChat = useCallback((id: string) => {
    setActiveId(id);
    setTab('chat');
    setFileError(null);
  }, []);

  const deleteChat = useCallback((id: string) => {
    setChats((existing) => existing.filter((chat) => chat.id !== id));
    setActiveId((current) => (current === id ? null : current));
    setProgressById(({ [id]: _removed, ...rest }) => rest);
    blobsRef.current.delete(id);
    timersRef.current.delete(id);
    void deleteAudio(id);
  }, []);

  const start = useCallback(
    (file: File) => {
      const validation = validateAudio(file);
      if (!validation.isValid) {
        setFileError(validation.message ?? 'Unsupported file.');
        return;
      }
      setFileError(null);

      let target = chatsRef.current.find((chat) => chat.id === activeId);
      if (!target || target.stage !== 'idle' || target.fileName) {
        const created = emptyChat();
        target = created;
        setChats((existing) => [...existing, created]);
        setActiveId(created.id);
      }
      const id = target.id;

      const segments = generateTranscript();
      const info = inspectAudio(file);
      const duration = Math.max(info?.estimatedDuration ?? 0, segments[segments.length - 1].start + 30);
      const now = Date.now();

      blobsRef.current.set(id, file);
      timersRef.current.delete(id);
      void saveAudio(id, file);

      setChats((existing) =>
        existing.map((chat) =>
          chat.id === id
            ? { ...chat, title: stripExtension(file.name), fileName: file.name, transcript: segments, duration, stage: 'transcribing', updatedAt: now }
            : chat,
        ),
      );
      setProgressById((current) => ({ ...current, [id]: 0 }));
      setTab('chat');
    },
    [activeId],
  );

  const ask = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question) return;
      let chat = chatsRef.current.find((item) => item.id === activeId);
      if (!chat) {
        const created = emptyChat();
        chat = created;
        setChats((existing) => [...existing, created]);
        setActiveId(created.id);
      }
      const id = chat.id;
      const youMessage = makeMessage('you', question);
      const botMessage = makeMessage('assistant', mockAnswer(question, chat.transcript));
      const now = Date.now();
      setChats((existing) =>
        existing.map((item) =>
          item.id === id
            ? {
                ...item,
                title: item.title === DEFAULT_TITLE ? (question.length > 32 ? `${question.slice(0, 32)}…` : question) : item.title,
                messages: [...item.messages, youMessage, botMessage],
                updatedAt: now,
              }
            : item,
        ),
      );
    },
    [activeId, makeMessage],
  );

  /* ---------- player ---------- */
  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const result = audio.play() as Promise<void> | undefined;
    result?.catch(() => setPlayerState((p) => ({ ...p, playing: false })));
  }, []);

  const pause = useCallback(() => audioRef.current?.pause(), []);

  const speed = playerState.speed;
  const cycleSpeed = useCallback(() => {
    const next = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length];
    if (audioRef.current) audioRef.current.playbackRate = next;
    setPlayerState((p) => ({ ...p, speed: next }));
  }, [speed]);

  const seek = useCallback((seconds: number) => {
    if (audioRef.current) {
      try {
        audioRef.current.currentTime = seconds;
      } catch {
        /* metadata not loaded yet */
      }
    }
    setPlayerState((p) => ({ ...p, currentTime: seconds }));
  }, []);

  const value = useMemo(
    () => ({
      chats,
      activeId,
      stage: active?.stage ?? ('idle' as Stage),
      progress: active ? (progressById[active.id] ?? 0) : 0,
      fileName: active?.fileName ?? null,
      fileError,
      transcript: active?.transcript ?? [],
      messages: active?.messages ?? [],
      player: { ...playerState, duration: playerState.duration || active?.duration || 0 },
      tab,
      setTab,
      newNote,
      selectChat,
      deleteChat,
      start,
      ask,
      play,
      pause,
      cycleSpeed,
      seek,
    }),
    [chats, activeId, active, progressById, fileError, playerState, tab, newNote, selectChat, deleteChat, start, ask, play, pause, cycleSpeed, seek],
  );

  return <RecordingContext.Provider value={value}>{children}</RecordingContext.Provider>;
}
