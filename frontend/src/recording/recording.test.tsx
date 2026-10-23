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

  it('2-5: transcribes, generates notes, then shows the ready view and player', async () => {
    const user = userEvent.setup();
    renderSignedIn();
    await user.upload(screen.getByLabelText(/recording file/i), new File(['x'], 'lecture.wav', { type: 'audio/wav' }));

    expect(screen.getByRole('progressbar', { name: /transcribing/i })).toBeInTheDocument();
    expect(await screen.findByRole('progressbar', { name: /generating notes/i }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/generate structured study notes/i)).toBeInTheDocument();

    expect(await screen.findByText(/transcription ready/i, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText('lecture.wav')).toBeInTheDocument();

    // Chat: ask a question, get a timestamped answer.
    await user.type(screen.getByLabelText(/message/i), 'What did the lecturer say about noise reduction?');
    await user.keyboard('{Enter}');
    expect(await screen.findByText(/^\[00:\d\d\]/)).toBeInTheDocument();

    // Transcriptions tab: player card.
    await user.click(screen.getByRole('tab', { name: /transcriptions/i }));
    const panel = screen.getByRole('tabpanel');
    expect(within(panel).getByText(/audio source: lecture\.wav/i)).toBeInTheDocument();
    expect(within(panel).getByText(/playback speed: 1x/i)).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: /change speed/i }));
    expect(within(panel).getByText(/playback speed: 1\.25x/i)).toBeInTheDocument();
  }, 20000);
});
