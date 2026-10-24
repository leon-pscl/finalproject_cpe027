import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

function mount(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('chats: live list, delete, persistence', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('lectureflow.session', JSON.stringify({ name: 'ada', identifier: 'ada' }));
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

  it('starts with an empty chat list, no mock data and no mascot', () => {
    mount('/');
    const chats = screen.getByRole('list', { name: 'Chats' });
    expect(within(chats).getByText(/no chats yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/conversation 1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/digital signal processing for students/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Assistant' })).not.toBeInTheDocument();
  });

  it('New Note adds a chat to the sidebar right away, and does not pile up empty ones', async () => {
    const user = userEvent.setup();
    mount('/');
    await user.click(within(screen.getByRole('navigation')).getByRole('button', { name: 'New Note' }));
    const chats = screen.getByRole('list', { name: 'Chats' });
    expect(within(chats).getAllByRole('listitem')).toHaveLength(1);
    expect(within(chats).getByText('New note')).toBeInTheDocument();
    await user.click(within(screen.getByRole('navigation')).getByRole('button', { name: 'New Note' }));
    expect(within(chats).getAllByRole('listitem')).toHaveLength(1);
  });

  it('keeps chats after a refresh (remount), and deleting removes them for good', async () => {
    const user = userEvent.setup();
    const first = mount('/new-transcription');
    await user.type(screen.getByLabelText(/message/i), 'What is signal quality?');
    await user.keyboard('{Enter}');
    const chats = screen.getByRole('list', { name: 'Chats' });
    expect(within(chats).getByText('What is signal quality?')).toBeInTheDocument();
    first.unmount();

    mount('/new-transcription');
    const again = screen.getByRole('list', { name: 'Chats' });
    expect(within(again).getByText('What is signal quality?')).toBeInTheDocument();
    await user.click(within(again).getByRole('button', { name: 'What is signal quality?' }));
    expect(screen.getAllByText('What is signal quality?').length).toBeGreaterThan(1); // sidebar + chat bubble

    await user.click(screen.getByRole('button', { name: /delete chat what is signal quality/i }));
    await user.click(screen.getByRole('button', { name: /confirm delete/i }));
    expect(within(screen.getByRole('list', { name: 'Chats' })).getByText(/no chats yet/i)).toBeInTheDocument();
  });

  it('Search and Recordings are separate pages', async () => {
    const user = userEvent.setup();
    mount('/');
    const nav = screen.getByRole('navigation', { name: /workspace/i });
    await user.click(within(nav).getByRole('link', { name: /^search$/i }));
    expect(await screen.findByRole('heading', { name: /search your lectures/i })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /recordings/i })).not.toHaveClass('bg-neutral-200');
    await user.click(within(nav).getByRole('link', { name: /recordings/i }));
    expect(await screen.findByRole('heading', { name: /your recordings/i })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /^search$/i })).not.toHaveClass('bg-neutral-200');
  });
});
