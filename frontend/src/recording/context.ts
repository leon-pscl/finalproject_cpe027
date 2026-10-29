// TESTING DEPLOYMENT
import { createContext } from 'react';
import type { TranscriptSegment } from '../services/mock';

export type Stage = 'idle' | 'transcribing' | 'generatingNotes' | 'ready';
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

  /** Which tab the right panel shows. */
  tab: Tab;
  setTab: (tab: Tab) => void;

  /** Starts a fresh chat (or reuses the active one if it is still empty). */
  newNote: () => void;
  selectChat: (id: string) => void;
  deleteChat: (id: string) => void;

  start: (file: File) => void;
  ask: (text: string) => void;
  play: () => void;
  pause: () => void;
  cycleSpeed: () => void;
  seek: (seconds: number) => void;
};

export const RecordingContext = createContext<RecordingContextValue | null>(null);
