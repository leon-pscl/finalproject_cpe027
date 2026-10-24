import { useMemo, useState } from 'react';
import { Search as SearchIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { NOTES_REQUEST } from '../recording/format';
import { useRecording } from '../recording/useRecording';
import { formatTimestamp } from '../services/mock';

type Hit = { key: string; label: string; text: string };
type Result = { chatId: string; title: string; hits: Hit[] };

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function Highlight({ text, query }: { text: string; query: string }) {
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'ig'));
  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === query.toLowerCase() ? <mark key={index}>{part}</mark> : <span key={index}>{part}</span>,
      )}
    </>
  );
}

export default function SearchPage() {
  const { chats, selectChat } = useRecording();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const needle = query.trim();

  const results = useMemo<Result[]>(() => {
    if (!needle) return [];
    const lower = needle.toLowerCase();
    const found: Result[] = [];
    for (const chat of chats) {
      const hits: Hit[] = [];
      if (chat.title.toLowerCase().includes(lower) || chat.fileName?.toLowerCase().includes(lower)) {
        hits.push({ key: 'name', label: 'Name', text: chat.fileName ?? chat.title });
      }
      for (const segment of chat.transcript) {
        if (segment.text.toLowerCase().includes(lower)) {
          hits.push({ key: segment.id, label: `Transcript ${formatTimestamp(segment.start)}`, text: segment.text });
        }
      }
      for (const message of chat.messages) {
        if (message.text !== NOTES_REQUEST && message.text.toLowerCase().includes(lower)) {
          hits.push({ key: `m-${message.id}`, label: message.from === 'you' ? 'You asked' : 'Answer', text: message.text });
        }
      }
      if (hits.length > 0) found.push({ chatId: chat.id, title: chat.title, hits });
    }
    return found;
  }, [chats, needle]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Search</p>
        <h1 className="mt-1 text-3xl font-semibold">Search your lectures</h1>
        <p className="mt-1 text-sm text-slate-600">Looks through recording names, transcripts, and your chats.</p>
      </header>

      <div className="relative">
        <label htmlFor="search-input" className="sr-only">
          Search recordings, transcripts and chats
        </label>
        <SearchIcon size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <input
          id="search-input"
          type="search"
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try “noise reduction”"
          className="h-12 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-3 text-base focus:outline-none focus:ring-2 focus:ring-teal-500"
        />
      </div>

      {!needle ? (
        <p className="text-sm text-slate-500">
          {chats.length === 0 ? 'Nothing to search yet. Upload a recording first.' : `Searching ${chats.length} ${chats.length === 1 ? 'chat' : 'chats'}.`}
        </p>
      ) : results.length === 0 ? (
        <p role="status" className="text-sm text-slate-600">
          No matches for “{needle}”.
        </p>
      ) : (
        <ul className="space-y-3" aria-label="Search results">
          {results.map((result) => (
            <li key={result.chatId} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <button
                type="button"
                onClick={() => {
                  selectChat(result.chatId);
                  navigate('/new-transcription');
                }}
                className="font-semibold text-teal-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
              >
                {result.title}
              </button>
              <ul className="mt-2 space-y-1.5 text-sm">
                {result.hits.slice(0, 3).map((hit) => (
                  <li key={hit.key} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3">
                    <span className="font-mono text-xs text-slate-500">{hit.label}</span>
                    <span>
                      <Highlight text={hit.text} query={needle} />
                    </span>
                  </li>
                ))}
                {result.hits.length > 3 ? <li className="text-xs text-slate-500">+{result.hits.length - 3} more in this chat</li> : null}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
