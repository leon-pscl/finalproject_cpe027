import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

describe('LectureFlow app', () => {
  beforeEach(() => {
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
    expect(screen.getAllByRole('link', { name: /process a lecture/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Recent lectures').length).toBeGreaterThan(0);
  });

  it('disables processing until required upload details are supplied', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/new-transcription']}>
        <App />
      </MemoryRouter>,
    );

    const startButton = screen.getByRole('button', { name: /start processing/i });
    expect(startButton).toBeDisabled();

    await user.type(screen.getByLabelText(/lecture title/i), 'Week 5 lecture');
    expect(startButton).toBeDisabled();
  });
});
