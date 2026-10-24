import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Bot, Gauge, Pause, PanelRightClose, Play } from 'lucide-react';
import { formatTimestamp } from '../services/mock';
import { useRecording } from '../recording/useRecording';
import type { Tab } from '../recording/context';

const playerBtn =
  'flex h-8 items-center gap-1.5 rounded px-2 text-xs hover:bg-white/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink disabled:opacity-40';

function PlayerCard() {
  const { fileName, stage, player, play, pause, cycleSpeed } = useRecording();
  const hasAudio = fileName !== null;

  if (!hasAudio) {
    return <p className="text-neutral-500">Transcriptions for the open recording will appear here.</p>;
  }

  return (
    <div className="rounded-3xl bg-accent/70 px-4 py-4 text-xs leading-5">
      <p className="break-all">Audio Source: {fileName}</p>
      <p className="flex items-center gap-1.5">
        Status:
        <span
          aria-hidden="true"
          className={`inline-block h-2.5 w-2.5 rounded-full ${stage === 'ready' ? 'bg-green-600' : 'bg-amber-500'}`}
        />
        {stage === 'ready' ? 'Enhanced (DSP Active)' : 'Processing…'}
      </p>
      <p>
        (Current Time: {formatTimestamp(player.currentTime)} / {formatTimestamp(player.duration)})
      </p>
      <p>Playback Speed: {player.speed}x</p>
      <div className="mt-4 flex items-center justify-between">
        <button type="button" onClick={cycleSpeed} className={playerBtn} aria-label={`Change speed, now ${player.speed}x`}>
          <Gauge size={14} aria-hidden="true" /> Speed
        </button>
        <button type="button" onClick={play} disabled={stage !== 'ready' || player.playing} className={playerBtn}>
          <Play size={14} aria-hidden="true" /> Play
        </button>
        <button type="button" onClick={pause} disabled={stage !== 'ready' || !player.playing} className={playerBtn}>
          <Pause size={14} aria-hidden="true" /> Pause
        </button>
      </div>
    </div>
  );
}

export default function RightPanel({ onCollapse }: { onCollapse: () => void }) {
  const { tab, setTab, messages, ask } = useRecording();
  const [draft, setDraft] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages, tab]);

  const send = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft.trim()) return;
    ask(draft);
    setDraft('');
    setTab('chat');
  };

  const tabClass = (active: boolean, side: 'l' | 'r') =>
    `h-8 px-5 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
      side === 'l' ? 'rounded-l-full' : 'rounded-r-full'
    } ${active ? 'bg-accent' : 'bg-paper'}`;

  const tabButton = (id: Tab, label: string, side: 'l' | 'r') => (
    <button type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className={tabClass(tab === id, side)}>
      {label}
    </button>
  );

  return (
    <aside aria-label="Assistant" className="flex h-full flex-col">
      {/* Header row: collapse toggle and tabs share one baseline (wireframes 4 and 5). */}
      <div className="grid grid-cols-[2rem_1fr_2rem] items-center gap-2 p-2">
        <button
          type="button"
          onClick={onCollapse}
          aria-label="Collapse assistant panel"
          className="flex h-8 w-8 items-center justify-center hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          <PanelRightClose size={18} aria-hidden="true" />
        </button>
        <div role="tablist" aria-label="Assistant views" className="mx-auto flex rounded-full border border-neutral-500">
          {tabButton('chat', 'Chat', 'l')}
          {tabButton('transcriptions', 'Transcriptions', 'r')}
        </div>
        <span />
      </div>

      <div className="flex min-h-0 flex-1 flex-col border-t border-ink p-3">
        <div role="tabpanel" className="flex-1 space-y-3 overflow-y-auto text-sm" aria-live="polite">
          {tab === 'chat' ? (
            messages.length === 0 ? (
              <p className="text-neutral-500">Ask a question about your lecture.</p>
            ) : (
              messages.map((message) =>
                message.from === 'you' ? (
                  <p key={message.id} className="rounded-md bg-neutral-200 px-3 py-2">
                    {message.text}
                  </p>
                ) : (
                  <div key={message.id} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-2">
                    <Bot size={18} aria-label="Assistant" className="mt-0.5" />
                    <p>{message.text}</p>
                  </div>
                ),
              )
            )
          ) : (
            <PlayerCard />
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={send} className="mt-3 rounded-md border border-dashed border-ink p-2">
          <label htmlFor="chat-input" className="sr-only">
            Message
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (draft.trim()) send(event as unknown as FormEvent<HTMLFormElement>);
              }
            }}
            placeholder="Input Text"
            className="min-h-10 w-full resize-none overflow-hidden border border-ink bg-paper px-2 py-2 text-sm shadow-[inset_2px_0_0_#000,inset_0_-2px_0_#000] focus:outline-none focus:ring-2 focus:ring-ink"
          />
        </form>
      </div>
    </aside>
  );
}
