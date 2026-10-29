import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

describe('LectureFlow app', () => {
  beforeEach(() => {
    // The initial route is protected: seed a demo session so the app renders signed in.
    window.localStorage.setItem('lectureflow.session', JSON.stringify({ identifier: 'demo', name: 'Demo' }));
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it('renders the dashboard and primary CTA', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getAllByText('LectureFlow').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /new note/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Continue where you left off').length).toBeGreaterThan(0);
  });

  it('disables processing until required upload details are supplied', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/new-transcription/advanced']}>
        <App />
      </MemoryRouter>,
    );

    const startButton = screen.getByRole('button', { name: /start processing/i });
    expect(startButton).toBeDisabled();

    await user.type(screen.getByLabelText(/lecture title/i), 'Week 5 lecture');
    expect(startButton).toBeDisabled();
  });
});
