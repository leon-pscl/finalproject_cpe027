import { useState, type FormEvent } from 'react';
import { ArrowRight } from 'lucide-react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';

const inputClass =
  'mt-1 block h-14 w-full border border-ink bg-paper px-3 font-sans text-base text-ink ' +
  'shadow-[inset_2px_0_0_#000,inset_0_-2px_0_#000] focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-2 focus:ring-offset-paper';

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? '/';

  if (user) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    setBusy(true);
    try {
      await login(identifier, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4 py-10 text-ink">
      <form
        onSubmit={handleSubmit}
        noValidate
        aria-label="Sign in"
        className="w-full max-w-[468px] rounded-md border border-dashed border-ink p-5"
      >
        <label htmlFor="identifier" className="block font-mono text-lg uppercase">
          Username / Email
          <input
            id="identifier"
            name="identifier"
            type="text"
            autoComplete="username"
            placeholder="user@example.com"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            className={inputClass}
          />
        </label>

        <label htmlFor="password" className="mt-10 block font-mono text-lg uppercase">
          Password
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={inputClass}
          />
        </label>

        <button
          type="button"
          onClick={() => setNotice('Password reset is not available in this demo.')}
          className="mt-2 text-sm underline focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
        >
          Forgot Password?
        </button>

        <div role="alert" className="min-h-6 pt-3 text-sm">
          {error}
        </div>
        <p aria-live="polite" className="min-h-0 text-sm">
          {notice}
        </p>

        <button
          type="submit"
          disabled={busy}
          className="mt-3 flex h-14 w-full items-center justify-center border border-ink font-mono text-lg uppercase hover:bg-ink hover:text-paper focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 disabled:opacity-50"
        >
          <span className="inline-flex items-center gap-2 border-b border-current">
            Continue
            <ArrowRight size={20} aria-hidden="true" />
          </span>
        </button>

        <p className="mt-4 text-center text-xs text-neutral-600">
          Demo sign-in: any username and password will work.
        </p>
      </form>
    </main>
  );
}
