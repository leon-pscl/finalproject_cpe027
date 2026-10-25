// RECORDING FILE FOR DEPLOYMENT
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

function renderSignedIn() {
  window.localStorage.setItem('lectureflow.session', JSON.stringify({ name: 'ada', identifier: 'ada' }));
  return render(
    <MemoryRouter initialEntries={['/new-transcription']}>
      <App />
    </MemoryRouter>,
  );
}

describe('recording flow (wireframes 1-5)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    window.localStorage.clear();
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: true,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    URL.createObjectURL = vi.fn(() => 'blob:demo');
    URL.revokeObjectURL = vi.fn();
    window.HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
    window.HTMLMediaElement.prototype.pause = vi.fn();
  });

  it('1: shows the drop zone and rejects unsupported files', async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderSignedIn();
    expect(screen.getByText(/drag recording here/i)).toBeInTheDocument();
    await user.upload(screen.getByLabelText(/recording file/i), new File(['x'], 'notes.txt', { type: 'text/plain' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/unsupported file type/i);
  });

  it('2-5: uploads to the API, shows real progress, then the returned transcript and player', async () => {
    // Test-only stub of the HTTP boundary; the real backend is covered by backend/tests.
    let polls = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Response.json({ id: 'job-1', status: 'queued', progress: 0, segments: [] }, { status: 202 });
      polls += 1;
      return Response.json(
        polls < 2
          ? { id: 'job-1', status: 'processing', progress: 0.4, segments: [], language: null, duration: 0, error: null }
          : {
              id: 'job-1',
              status: 'completed',
              progress: 1,
              language: 'en',
              duration: 95,
              error: null,
              dsp: { applied: true, seconds: 1.2, snr_est_before_db: 11.5, snr_est_after_db: 17.25 },
              segments: [
                { id: 'seg-1', start: 12, end: 20, text: 'Noise reduction happens before recognition.', confidence: 0.9 },
                { id: 'seg-2', start: 26, end: 40, text: 'The short-time Fourier transform uses windows.', confidence: 0.8 },
              ],
            },
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const user = userEvent.setup();
    renderSignedIn();
    await user.upload(screen.getByLabelText(/recording file/i), new File(['x'], 'lecture.wav', { type: 'audio/wav' }));

    expect(screen.getByRole('progressbar', { name: /transcribing/i })).toBeInTheDocument();
    expect(await screen.findByText(/transcription ready/i, {}, { timeout: 6000 })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe('/api/transcriptions');
    expect(screen.getByText('lecture.wav')).toBeInTheDocument();
    expect(screen.getByText('Noise reduction happens before recognition.')).toBeInTheDocument();
    expect(screen.queryByText(/generating notes/i)).not.toBeInTheDocument();
    expect(screen.getByText(/audio enhanced in 1\.2 s \(estimated snr 11\.5 → 17\.3 db\)/i)).toBeInTheDocument();

    // Chat: the answer is a real transcript segment with its timestamp.
    await user.type(screen.getByLabelText(/message/i), 'What did the lecturer say about noise reduction?');
    await user.keyboard('{Enter}');
    expect(await screen.findByText(/^\[00:12\] Noise reduction/)).toBeInTheDocument();

    // Transcriptions tab: player card.
    await user.click(screen.getByRole('tab', { name: /transcriptions/i }));
    const panel = screen.getByRole('tabpanel');
    expect(within(panel).getByText(/audio source: lecture\.wav/i)).toBeInTheDocument();
    expect(within(panel).getByText(/playback speed: 1x/i)).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: /change speed/i }));
    expect(within(panel).getByText(/playback speed: 1\.25x/i)).toBeInTheDocument();
  }, 20000);

  it('shows the server error and returns to the drop zone when transcription cannot start', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Response.json({ detail: 'File exceeds the 300 MB limit.' }, { status: 413 })));
    const user = userEvent.setup();
    renderSignedIn();
    await user.upload(screen.getByLabelText(/recording file/i), new File(['x'], 'big.wav', { type: 'audio/wav' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/exceeds the 300 MB limit/i);
    expect(screen.getByText(/drag recording here/i)).toBeInTheDocument();
  });
});
