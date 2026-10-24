/** The message the app sends on the user's behalf when note generation starts. */
export const NOTES_REQUEST = 'Generate structured study notes with key definitions.';

export function stripExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}

/** "just now", "5 min ago", "3 h ago", "2 d ago", else a short date. */
export function timeAgo(timestamp: number, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - timestamp) / 1000));
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return new Date(timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function stageLabel(stage: 'idle' | 'transcribing' | 'generatingNotes' | 'ready'): string {
  switch (stage) {
    case 'ready':
      return 'Ready';
    case 'transcribing':
      return 'Transcribing';
    case 'generatingNotes':
      return 'Generating notes';
    default:
      return 'Empty';
  }
}
