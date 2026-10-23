import { useState } from 'react';
import { PanelLeftOpen, PanelRightOpen } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import RightPanel from '../components/RightPanel';
import Sidebar from '../components/Sidebar';

const isDesktop = () =>
  typeof window.matchMedia !== 'function' || window.matchMedia('(min-width: 1024px)').matches;

const openBtn =
  'flex h-8 w-8 items-center justify-center border border-ink bg-paper hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink';

export default function AppShell() {
  const [leftOpen, setLeftOpen] = useState(isDesktop);
  const [rightOpen, setRightOpen] = useState(isDesktop);
  const anyDrawerOpen = (leftOpen || rightOpen) && !isDesktop();

  return (
    <div className="flex h-screen bg-paper text-ink">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {leftOpen ? (
        <div className="fixed inset-y-0 left-0 z-30 w-60 border-r border-neutral-400 bg-paper lg:static lg:z-auto lg:w-48 lg:shrink-0">
          <Sidebar onCollapse={() => setLeftOpen(false)} />
        </div>
      ) : null}

      <main id="main-content" className="relative min-w-0 flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 flex justify-between p-2">
          {leftOpen ? <span /> : (
            <button type="button" onClick={() => setLeftOpen(true)} aria-label="Open sidebar" className={openBtn}>
              <PanelLeftOpen size={18} aria-hidden="true" />
            </button>
          )}
          {rightOpen ? <span /> : (
            <button type="button" onClick={() => setRightOpen(true)} aria-label="Open assistant panel" className={openBtn}>
              <PanelRightOpen size={18} aria-hidden="true" />
            </button>
          )}
        </div>
        <div className="px-4 pb-8 sm:px-6">
          <Outlet />
        </div>
      </main>

      {rightOpen ? (
        <div className="fixed inset-y-0 right-0 z-30 w-80 max-w-full border-l border-ink bg-paper lg:static lg:z-auto lg:w-72 lg:shrink-0">
          <RightPanel onCollapse={() => setRightOpen(false)} />
        </div>
      ) : null}

      {anyDrawerOpen ? (
        <button
          type="button"
          aria-label="Close panels"
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={() => {
            setLeftOpen(false);
            setRightOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
