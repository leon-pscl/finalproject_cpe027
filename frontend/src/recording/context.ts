import { createContext } from 'react';
import type { TranscriptSegment } from '../services/api';

export type Stage = 'idle' | 'dsp' | 'transcribing' | 'generatingNotes' | 'ready';
export type Tab = 'chat' | 'transcriptions';
export type ChatMessage = { id: number; from: 'you' | 'assistant'; text: string };
export type PlayerState = { currentTime: number; duration: number; playing: boolean; speed: number };

export type AudioAsset = {
  kind: 'original' | 'processed';
  url: string | null;
  storagePath: string | null;
  available: boolean;
  pending: boolean;
};

/** One note session = one chat in the sidebar. Persisted per user. */
export type ChatSession = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  stage: Stage;
  fileName: string | null;
  /** Backend transcription job for this chat (present while processing, kept for cleanup). */
  jobId?: string;
  notesReady?: boolean;
  /** Fallback duration in seconds (used when the audio element has no metadata). */
  duration: number;
  storagePath: string | null;
  transcript: TranscriptSegment[];
  messages: ChatMessage[];
};

export type RecordingContextValue = {
  chats: ChatSession[];
  activeId: string | null;

  // Derived from the active chat (idle defaults when there is none).
  stage: Stage;
  /** 0-100 progress of the active chat's current loading stage */
  progress: number;
  fileName: string | null;
  fileError: string | null;
  transcript: TranscriptSegment[];
  messages: ChatMessage[];
  player: PlayerState;
  jobId: string | null;
  notesReady: boolean;

  /** Which tab the right panel shows. */
  tab: Tab;
  setTab: (tab: Tab) => void;

  /** Starts a fresh chat (or reuses the active one if it is still empty). */
  newNote: () => void;
  selectChat: (id: string) => void;
  deleteChat: (id: string) => void;

  start: (file: File, processingOptions?: { high_pass_enabled?: boolean; high_pass_cutoff_hz?: number; background_noise_reduction_enabled?: boolean; }) => Promise<void>;
  ask: (text: string) => Promise<void>;
  setNotesReady: (ready: boolean) => void;
  play: () => void;
  pause: () => void;
  cycleSpeed: () => void;
  seek: (seconds: number) => void;
  seekProcessed: (seconds: number) => void;
  registerProcessedAudio: (element: HTMLAudioElement | null) => void;
  dspUrl: string | null;
};

export const RecordingContext = createContext<RecordingContextValue | null>(null);
