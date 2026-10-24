import { useState } from 'react';
import { Check, Loader2, Mic, PanelLeftClose, Pencil, Search, Settings, Trash2, X } from 'lucide-react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useRecording } from '../recording/useRecording';

const itemClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 items-center gap-3 px-2 text-[15px] hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
    isActive ? 'bg-neutral-200' : ''
  }`;

const iconBtn =
  'flex h-8 w-8 shrink-0 items-center justify-center hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink';

export default function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const { user, logout } = useAuth();
  const { chats, activeId, newNote, selectChat, deleteChat } = useRecording();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const ordered = [...chats].sort((a, b) => b.createdAt - a.createdAt);

  const openChat = (id: string) => {
    selectChat(id);
    navigate('/new-transcription');
  };

  return (
    <nav aria-label="Workspace" className="flex h-full flex-col">
      <div className="flex justify-end p-2">
        <button type="button" onClick={onCollapse} aria-label="Collapse sidebar" className={iconBtn}>
          <PanelLeftClose size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="px-1">
        <button
          type="button"
          onClick={() => {
            newNote();
            navigate('/new-transcription');
          }}
          className="flex min-h-11 w-full items-center gap-3 px-2 text-left text-[15px] hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          <Pencil size={18} aria-hidden="true" /> New Note
        </button>
        <NavLink to="/search" className={itemClass}>
          <Search size={18} aria-hidden="true" /> Search
        </NavLink>
        <NavLink to="/recordings" className={itemClass}>
          <Mic size={18} aria-hidden="true" /> Recordings
        </NavLink>
      </div>

      <h2 className="mt-3 px-2 text-xs text-neutral-500">Chats</h2>
      <ul aria-label="Chats" className="min-h-0 flex-1 overflow-y-auto px-1">
        {ordered.length === 0 ? (
          <li className="px-2 py-2 text-sm text-neutral-500">No chats yet. Click New Note to start.</li>
        ) : null}
        {ordered.map((chat) => {
          const current = chat.id === activeId && pathname === '/new-transcription';
          const busy = chat.stage === 'transcribing' || chat.stage === 'generatingNotes';
          return (
            <li key={chat.id} className={`flex items-center ${current ? 'bg-neutral-200' : ''}`}>
              <button
                type="button"
                onClick={() => openChat(chat.id)}
                aria-current={current ? 'page' : undefined}
                className="flex min-h-10 min-w-0 flex-1 items-center gap-2 px-2 text-left text-[15px] hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
              >
                {busy ? <Loader2 size={14} className="shrink-0 animate-spin" aria-label="Processing" /> : null}
                <span className="truncate">{chat.title}</span>
              </button>
              {confirmId === chat.id ? (
                <>
                  <button
                    type="button"
                    aria-label={`Confirm delete ${chat.title}`}
                    onClick={() => {
                      deleteChat(chat.id);
                      setConfirmId(null);
                    }}
                    className={`${iconBtn} text-red-700`}
                  >
                    <Check size={16} aria-hidden="true" />
                  </button>
                  <button type="button" aria-label="Cancel delete" onClick={() => setConfirmId(null)} className={iconBtn}>
                    <X size={16} aria-hidden="true" />
                  </button>
                </>
              ) : (
                <button type="button" aria-label={`Delete chat ${chat.title}`} onClick={() => setConfirmId(chat.id)} className={iconBtn}>
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              )}
            </li>
          );
        })}
      </ul>

      <div className="relative border-t border-neutral-400 p-2">
        {menuOpen ? (
          <div className="absolute bottom-full left-2 right-2 mb-1 border border-ink bg-paper">
            <button
              type="button"
              onClick={logout}
              className="block min-h-11 w-full px-3 text-left text-sm hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
            >
              Sign out
            </button>
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink font-mono text-xs uppercase"
            >
              {user?.name.charAt(0)}
            </span>
            <span className="truncate text-[15px]">{user?.name}</span>
          </div>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="Account settings"
            aria-expanded={menuOpen}
            className={iconBtn}
          >
            <Settings size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
    </nav>
  );
}
