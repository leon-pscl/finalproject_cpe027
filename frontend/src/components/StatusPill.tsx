import { stageLabel } from '../recording/format';
import type { Stage } from '../recording/context';

const tone: Record<Stage, string> = {
  ready: 'bg-emerald-100 text-emerald-800',
  transcribing: 'bg-amber-100 text-amber-800',
  generatingNotes: 'bg-amber-100 text-amber-800',
  idle: 'bg-slate-100 text-slate-600',
};

export default function StatusPill({ stage }: { stage: Stage }) {
  return <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone[stage]}`}>{stageLabel(stage)}</span>;
}
