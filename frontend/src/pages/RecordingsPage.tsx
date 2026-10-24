import { useState } from 'react';
import { FileAudio, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import StatusPill from '../components/StatusPill';
import { timeAgo } from '../recording/format';
import { useRecording } from '../recording/useRecording';
import { formatTimestamp } from '../services/mock';

export default function RecordingsPage() {
  const { chats, selectChat, deleteChat, newNote } = useRecording();
  const navigate = useNavigate();
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const recordings = chats.filter((chat) => chat.fileName).sort((a, b) => b.createdAt - a.createdAt);

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Recordings</p>
        <h1 className="mt-1 text-3xl font-semibold">Your recordings</h1>
        <p className="mt-1 text-sm text-slate-600">Each recording is saved with its transcript and chat. Deleting one removes both.</p>
      </header>

      {recordings.length === 0 ? (
        <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
          <FileAudio size={30} className="mb-3 text-slate-400" aria-hidden="true" />
          <p className="font-medium">No recordings yet</p>
          <button
            type="button"
            onClick={() => {
              newNote();
              navigate('/new-transcription');
            }}
            className="mt-3 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            Upload your first recording
          </button>
        </div>
      ) : (
        <ul className="space-y-3">
          {recordings.map((chat) => (
            <li key={chat.id} className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <h2 className="truncate font-semibold">{chat.title}</h2>
                  <StatusPill stage={chat.stage} />
                </div>
                <p className="mt-1 truncate text-sm text-slate-500">
                  {chat.fileName} · {formatTimestamp(chat.duration)} · added {timeAgo(chat.createdAt)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    selectChat(chat.id);
                    navigate('/new-transcription');
                  }}
                  className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  Open
                </button>
                {confirmId === chat.id ? (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        deleteChat(chat.id);
                        setConfirmId(null);
                      }}
                      className="rounded-xl border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500"
                    >
                      Confirm delete
                    </button>
                    <button type="button" onClick={() => setConfirmId(null)} className="rounded-xl border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500">
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmId(chat.id)}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    <Trash2 size={15} aria-hidden="true" /> Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
