import { createContext } from 'react';
import type { TranscriptSegment } from '../services/mock';

export type Stage = 'idle' | 'transcribing' | 'generatingNotes' | 'ready';
export type Tab = 'chat' | 'transcriptions';
export type ChatMessage = { id: number; from: 'you' | 'assistant'; text: string };
export type PlayerState = { currentTime: number; duration: number; playing: boolean; speed: number };

export type RecordingContextValue = {
  stage: Stage;
  /** 0-100 progress of the current loading stage */
  progress: number;
  fileName: string | null;
  fileError: string | null;
  transcript: TranscriptSegment[];
  messages: ChatMessage[];
  player: PlayerState;
  /** Which tab the right panel shows. Lives here so the page can switch it. */
  tab: Tab;
  setTab: (tab: Tab) => void;
  start: (file: File) => void;
  reset: () => void;
  ask: (text: string) => void;
  play: () => void;
  pause: () => void;
  cycleSpeed: () => void;
  seek: (seconds: number) => void;
};

export const RecordingContext = createContext<RecordingContextValue | null>(null);
