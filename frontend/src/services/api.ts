import type { TranscriptSegment } from './mock';

export type JobStatus = {
  id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number; // 0..1
  language: string | null;
  duration: number;
  segments: Array<{ id: string; start: number; end: number; text: string; confidence: number }>;
  error: string | null;
  phase?: string;
  dsp?: { applied: boolean; snr_est_before_db?: number; snr_est_after_db?: number; speech_ratio?: number; seconds?: number; error?: string | null } | null;
};

async function failure(res: Response): Promise<Error> {
  let detail = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {
    /* non-JSON error body */
  }
  return new Error(detail);
}

/** Uploads the recording; the backend transcribes it with a pretrained Whisper model. */
export async function submitTranscription(file: File): Promise<{ id: string }> {
  const body = new FormData();
  body.append('file', file);
  const res = await fetch('/api/transcriptions', { method: 'POST', body });
  if (!res.ok) throw await failure(res);
  return res.json();
}

/** Returns null when the backend no longer knows the job (e.g. it restarted). */
export async function fetchJob(id: string): Promise<JobStatus | null> {
  const res = await fetch(`/api/transcriptions/${encodeURIComponent(id)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw await failure(res);
  return res.json();
}

export async function deleteJob(id: string): Promise<void> {
  try {
    await fetch(`/api/transcriptions/${encodeURIComponent(id)}`, { method: 'DELETE' });
  } catch {
    /* best effort */
  }
}

export const toTranscript = (job: JobStatus): TranscriptSegment[] =>
  job.segments.map((s) => ({ id: s.id, start: s.start, end: s.end, speaker: 'Lecturer', text: s.text, confidence: s.confidence }));
