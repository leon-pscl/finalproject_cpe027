import { useEffect, useRef, useState } from 'react';
import { animate } from 'animejs';
import { PanelLeftOpen, PanelRightOpen } from 'lucide-react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import RightPanel from '../components/RightPanel';
import Sidebar from '../components/Sidebar';
import { RecordingProvider } from '../recording/RecordingProvider';

const isDesktop = () =>
  typeof window.matchMedia !== 'function' || window.matchMedia('(min-width: 1024px)').matches;

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const openBtn =
  'flex h-8 w-8 items-center justify-center border border-ink bg-paper hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink';

export default function AppShell() {
  return (
    <RecordingProvider>
      <ShellLayout />
    </RecordingProvider>
  );
}

function ShellLayout() {
  const [leftOpen, setLeftOpen] = useState(isDesktop);
  const [rightOpen, setRightOpen] = useState(isDesktop);
  const anyDrawerOpen = (leftOpen || rightOpen) && !isDesktop();

  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const leftInitial = useRef(true);
  const rightInitial = useRef(true);
  const initialAnimated = useRef(false);
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    if (!prefersReducedMotion()) {
      if (leftOpen && leftRef.current) {
        animate(leftRef.current, { translateX: ['0%', '-100%'], opacity: [1, 0], duration: 240, ease: 'in(3)' });
      }
      if (rightOpen && rightRef.current) {
        animate(rightRef.current, { translateX: ['0%', '100%'], opacity: [1, 0], duration: 240, ease: 'in(3)' });
      }
    }
    window.setTimeout(() => {
      logout();
      navigate('/login', { replace: true });
    }, prefersReducedMotion() ? 0 : 280);
  };

  useEffect(() => {
    if (initialAnimated.current) return;
    initialAnimated.current = true;
    if (prefersReducedMotion()) return;
    if (leftOpen && leftRef.current) {
      animate(leftRef.current, { translateX: ['-100%', '0%'], opacity: [0, 1], duration: 300, ease: 'out(3)' });
    }
    if (rightOpen && rightRef.current) {
      animate(rightRef.current, { translateX: ['100%', '0%'], opacity: [0, 1], duration: 300, ease: 'out(3)' });
    }
  }, [leftOpen, rightOpen]);

  useEffect(() => {
    if (leftInitial.current) {
      leftInitial.current = false;
      return;
    }
    if (!leftOpen) return;
    const el = leftRef.current;
    if (!el || prefersReducedMotion()) return;
    animate(el, {
      translateX: ['-100%', '0%'],
      opacity: [0, 1],
      duration: 240,
      ease: 'out(3)',
    });
  }, [leftOpen]);

  useEffect(() => {
    if (rightInitial.current) {
      rightInitial.current = false;
      return;
    }
    if (!rightOpen) return;
    const el = rightRef.current;
    if (!el || prefersReducedMotion()) return;
    animate(el, {
      translateX: ['100%', '0%'],
      opacity: [0, 1],
      duration: 240,
      ease: 'out(3)',
    });
  }, [rightOpen]);

  const collapseLeft = () => {
    const el = leftRef.current;
    if (!el || prefersReducedMotion()) {
      setLeftOpen(false);
      return;
    }
    animate(el, {
      translateX: ['0%', '-100%'],
      opacity: [1, 0],
      duration: 240,
      ease: 'in(3)',
      onComplete: () => setLeftOpen(false),
    });
    // Fallback so the panel still unmounts if the animation callback is delayed.
    window.setTimeout(() => setLeftOpen(false), 320);
  };

  const collapseRight = () => {
    const el = rightRef.current;
    if (!el || prefersReducedMotion()) {
      setRightOpen(false);
      return;
    }
    animate(el, {
      translateX: ['0%', '100%'],
      opacity: [1, 0],
      duration: 240,
      ease: 'in(3)',
      onComplete: () => setRightOpen(false),
    });
    window.setTimeout(() => setRightOpen(false), 320);
  };

  return (
    <div className="flex h-screen bg-paper text-ink">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {leftOpen ? (
        <div
          ref={leftRef}
          className="fixed inset-y-0 left-0 z-30 w-60 border-r border-neutral-400 bg-paper lg:static lg:z-auto lg:w-48 lg:shrink-0"
        >
          <Sidebar onCollapse={collapseLeft} onLogout={handleLogout} />
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
        <div
          ref={rightRef}
          className="fixed inset-y-0 right-0 z-30 w-80 max-w-full border-l border-ink bg-paper lg:static lg:z-auto lg:w-72 lg:shrink-0"
        >
          <RightPanel onCollapse={collapseRight} />
        </div>
      ) : null}

      {anyDrawerOpen ? (
        <button
          type="button"
          aria-label="Close panels"
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={() => {
            collapseLeft();
            collapseRight();
          }}
        />
      ) : null}
    </div>
  );
}