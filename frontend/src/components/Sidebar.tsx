import { useState } from 'react';
import { Mic, PanelLeftClose, Pencil, Search, Settings } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useRecording } from '../recording/useRecording';

const demoChats = ['Conversation 1', 'Conversation 2'];

const itemClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 items-center gap-3 px-2 text-[15px] hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
    isActive ? 'bg-neutral-200' : ''
  }`;

export default function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const { user, logout } = useAuth();
  const { reset } = useRecording();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav aria-label="Workspace" className="flex h-full flex-col">
      <div className="flex justify-end p-2">
        <button
          type="button"
          onClick={onCollapse}
          aria-label="Collapse sidebar"
          className="flex h-8 w-8 items-center justify-center hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          <PanelLeftClose size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="px-1">
        <NavLink to="/new-transcription" onClick={reset} className={itemClass}>
          <Pencil size={18} aria-hidden="true" /> New Note
        </NavLink>
        <NavLink to="/recent-lectures" className={itemClass}>
          <Search size={18} aria-hidden="true" /> Search
        </NavLink>
        <NavLink to="/recent-lectures" end className={itemClass}>
          <Mic size={18} aria-hidden="true" /> Recordings
        </NavLink>
      </div>

      <h2 className="mt-3 px-2 text-xs text-neutral-500">Chats</h2>
      <ul className="px-1">
        {demoChats.map((chat) => (
          <li key={chat}>
            <Link
              to="/"
              className="flex min-h-10 items-center px-2 text-[15px] hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
            >
              {chat}
            </Link>
          </li>
        ))}
      </ul>

      <div className="relative mt-auto border-t border-neutral-400 p-2">
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
            className="flex h-8 w-8 items-center justify-center hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
          >
            <Settings size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
    </nav>
  );
}
