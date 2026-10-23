import { useState, type FormEvent } from 'react';
import { PanelRightClose } from 'lucide-react';

type Tab = 'chat' | 'transcriptions';
type Message = { id: number; from: 'you' | 'assistant'; text: string };

function Mascot() {
  return (
    <svg viewBox="0 0 120 100" role="img" aria-label="Assistant" className="h-28 w-32">
      <g fill="none" stroke="#000" strokeWidth="1.5">
        <path d="M60 24V8h14" />
        <rect x="30" y="24" width="60" height="50" rx="14" />
        <path d="M14 50h16M90 50h16" />
        <path d="M52 42v10M68 42v10" strokeWidth="2" />
      </g>
    </svg>
  );
}

export default function RightPanel({ onCollapse }: { onCollapse: () => void }) {
  const [tab, setTab] = useState<Tab>('chat');
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);

  const send = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    const id = Date.now();
    setMessages((current) => [
      ...current,
      { id, from: 'you', text },
      { id: id + 1, from: 'assistant', text: 'Demo reply: lecture Q&A is not connected yet.' },
    ]);
    setDraft('');
  };

  const tabClass = (active: boolean, side: 'l' | 'r') =>
    `h-8 px-6 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
      side === 'l' ? 'rounded-l-full' : 'rounded-r-full'
    } ${active ? 'bg-accent' : 'bg-paper'}`;

  return (
    <aside aria-label="Assistant" className="flex h-full flex-col">
      <div className="p-2">
        <button
          type="button"
          onClick={onCollapse}
          aria-label="Collapse assistant panel"
          className="flex h-8 w-8 items-center justify-center hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          <PanelRightClose size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="mx-auto flex h-44 w-4/5 items-start justify-center border border-ink">
        <Mascot />
      </div>

      <div className="mt-6 flex min-h-0 flex-1 flex-col border-t border-ink p-3">
        <div role="tablist" aria-label="Assistant views" className="mx-auto flex rounded-full border border-neutral-500">
          <button type="button" role="tab" aria-selected={tab === 'chat'} onClick={() => setTab('chat')} className={tabClass(tab === 'chat', 'l')}>
            Chat
          </button>
          <button type="button" role="tab" aria-selected={tab === 'transcriptions'} onClick={() => setTab('transcriptions')} className={tabClass(tab === 'transcriptions', 'r')}>
            Transcriptions
          </button>
        </div>

        <div role="tabpanel" className="mt-3 flex-1 space-y-2 overflow-y-auto text-sm" aria-live="polite">
          {tab === 'chat' ? (
            messages.length === 0 ? (
              <p className="text-neutral-500">Ask a question about your lecture.</p>
            ) : (
              messages.map((message) => (
                <p key={message.id} className={message.from === 'you' ? 'text-right' : ''}>
                  <span className="inline-block max-w-full border border-neutral-400 px-2 py-1">{message.text}</span>
                </p>
              ))
            )
          ) : (
            <p className="text-neutral-500">Transcriptions for the open recording will appear here.</p>
          )}
        </div>

        <form onSubmit={send} className="mt-3 rounded-md border border-dashed border-ink p-2">
          <label htmlFor="chat-input" className="sr-only">
            Message
          </label>
          <input
            id="chat-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Input Text"
            className="h-10 w-full border border-ink bg-paper px-2 text-sm shadow-[inset_2px_0_0_#000,inset_0_-2px_0_#000] focus:outline-none focus:ring-2 focus:ring-ink"
          />
        </form>
      </div>
    </aside>
  );
}
