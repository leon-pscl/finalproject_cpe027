import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Bot, Gauge, Pause, PanelRightClose, Play } from 'lucide-react';
import { formatTimestamp } from '../services/mock';
import { useRecording } from '../recording/useRecording';
import type { Tab } from '../recording/context';

const playerBtn =
  'flex h-8 items-center gap-1.5 rounded px-2 text-xs font-mono hover:bg-neutral-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink disabled:opacity-40';

function PlayerCard() {
  const { fileName, stage, player, play, pause, cycleSpeed, dspUrl } = useRecording();
  const hasAudio = fileName !== null;

  if (!hasAudio) {
    return <p className="text-neutral-500">Transcriptions for the open recording will appear here.</p>;
  }

  return (<>
    <div className="rounded-2xl border border-ink bg-paper px-4 py-4 font-mono text-xs leading-5">
      <p className="break-all">Audio Source: {fileName}</p>
      <p className="flex items-center gap-1.5">
        Status:
        <span
          aria-hidden="true"
          className={`inline-block h-2.5 w-2.5 rounded-full ${stage === 'ready' ? 'bg-ink' : 'bg-neutral-500'}`}
        />
        {stage === 'ready' ? 'Enhanced (DSP Active)' : 'Processing…'}
      </p>
      <p>(Current Time: {formatTimestamp(player.currentTime)} / {formatTimestamp(player.duration)})</p>
      <p>DSP Playback Speed: {player.speed}x</p>
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
    {/* DSP‑enhanced player */}
    <div className="rounded-2xl border border-ink bg-paper px-4 py-4 font-mono text-xs leading-5 mt-4">
      <p className="break-all">Processed Audio: {fileName}</p>
      <p className="flex items-center gap-1.5">
        Status:
        <span
          aria-hidden="true"
          className={`inline-block h-2.5 w-2.5 rounded-full ${stage === 'ready' ? 'bg-ink' : 'bg-neutral-500'}`}
        />
        {stage === 'ready' ? 'Enhanced (DSP Active)' : 'Processing…'}
      </p>
      <p>(Current Time: {formatTimestamp(player.currentTime)} / {formatTimestamp(player.duration)})</p>
      {dspUrl && <ProcessedAudioPlayer url={dspUrl} />}
    </div>
  </>);
}

function ProcessedAudioPlayer({ url }: { url: string }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrent(audio.currentTime);
    const onMeta = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    const onEnded = () => setPlaying(false);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('ended', onEnded);
    };
  }, [url]);

  return (
    <div className="rounded-2xl border border-ink bg-paper px-4 py-4 font-mono text-xs leading-5">
      <audio ref={audioRef} src={url} preload="metadata" className="sr-only" />
      <p className="text-neutral-500">Processed audio</p>
      <div className="mt-3 grid min-w-0 grid-cols-[auto,minmax(0,1fr),auto] items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (!audioRef.current) return;
            if (playing) {
              audioRef.current.pause();
            } else {
              void audioRef.current.play();
            }
            setPlaying(!playing);
          }}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded border border-ink bg-ink px-3 font-mono text-xs font-medium text-paper hover:bg-neutral-800"
        >
          {playing ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
          {playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={current}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setCurrent(next);
          }}
          aria-label="Processed audio position"
          className="min-w-0 h-1 w-full accent-ink"
        />
        <span className="shrink-0 font-mono text-xs text-neutral-500">
          {formatTimestamp(current)} / {formatTimestamp(duration)}
        </span>
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
    } ${active ? 'bg-slate-200' : 'bg-paper'}`;

  const tabButton = (id: Tab, label: string, side: 'l' | 'r') => (
    <button type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className={tabClass(tab === id, side)}>
      {label}
    </button>
  );

  return (<>
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
    </>
  );
}
