import { FileAudio, MessageSquare, Mic, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import StatusPill from '../components/StatusPill';
import { NOTES_REQUEST, timeAgo } from '../recording/format';
import { useRecording } from '../recording/useRecording';

const card = 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm';

export default function HomePage() {
  const { chats, newNote, selectChat } = useRecording();
  const navigate = useNavigate();

  const open = (id: string) => {
    selectChat(id);
    navigate('/new-transcription');
  };

  const recordings = chats.filter((chat) => chat.fileName);
  const readyCount = recordings.filter((chat) => chat.stage === 'ready').length;
  const recent = [...chats].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 4);

  const questions = chats
    .flatMap((chat) =>
      chat.messages.filter((m) => m.from === 'you' && m.text !== NOTES_REQUEST).map((m) => ({ ...m, chatId: chat.id, chatTitle: chat.title })),
    )
    .sort((a, b) => b.id - a.id)
    .slice(0, 5);
  const questionCount = chats.reduce(
    (total, chat) => total + chat.messages.filter((m) => m.from === 'you' && m.text !== NOTES_REQUEST).length,
    0,
  );

  const stats = [
    { label: 'Recordings', value: recordings.length, icon: FileAudio },
    { label: 'Notes ready', value: readyCount, icon: Mic },
    { label: 'Questions asked', value: questionCount, icon: MessageSquare },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section className={`${card} flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between`}>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Academic productivity</p>
          <h1 className="text-3xl font-semibold tracking-tight">LectureFlow</h1>
          <p className="mt-2 text-slate-600">Turn recorded lectures into clean transcripts, traceable notes, and study-ready summaries.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            newNote();
            navigate('/new-transcription');
          }}
          className="inline-flex min-h-[44px] shrink-0 items-center justify-center gap-2 rounded-xl bg-teal-600 px-5 py-3 text-sm font-medium text-white hover:bg-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
        >
          <Plus size={18} aria-hidden="true" /> New note
        </button>
      </section>

      <section aria-label="Your activity" className="grid gap-4 sm:grid-cols-3">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className={`${card} flex items-center gap-4`}>
            <Icon size={22} className="text-teal-700" aria-hidden="true" />
            <div>
              <p className="text-2xl font-semibold leading-none">{value}</p>
              <p className="mt-1 text-sm text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </section>

      <section className={card}>
        <h2 className="mb-4 text-xl font-semibold">Continue where you left off</h2>
        {recent.length === 0 ? (
          <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
            <FileAudio size={30} className="mb-3 text-slate-400" aria-hidden="true" />
            <p className="font-medium">Nothing here yet</p>
            <p className="mt-1 max-w-sm text-sm text-slate-600">Start a new note and drop in a lecture recording. Your chats and transcripts are saved automatically.</p>
          </div>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {recent.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  onClick={() => open(chat.id)}
                  className="flex h-full w-full flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left hover:shadow-md focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="line-clamp-2 font-semibold">{chat.title}</span>
                    <StatusPill stage={chat.stage} />
                  </span>
                  <span className="truncate text-sm text-slate-500">{chat.fileName ?? 'No recording yet'}</span>
                  <span className="text-xs text-slate-500">
                    {chat.messages.length} {chat.messages.length === 1 ? 'message' : 'messages'} · {timeAgo(chat.updatedAt)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {questions.length > 0 ? (
        <section className={card}>
          <h2 className="mb-3 text-xl font-semibold">Recent questions</h2>
          <ul className="divide-y divide-slate-100">
            {questions.map((question) => (
              <li key={question.id}>
                <button
                  type="button"
                  onClick={() => open(question.chatId)}
                  className="flex w-full items-baseline justify-between gap-4 py-2.5 text-left text-sm hover:text-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
                >
                  <span className="truncate">{question.text}</span>
                  <span className="shrink-0 text-xs text-slate-500">{question.chatTitle}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
