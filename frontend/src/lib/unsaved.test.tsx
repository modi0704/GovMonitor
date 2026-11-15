import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach } from 'vitest';
import { api } from '../api/client';
import LoadingBar from '../layout/LoadingBar';
import { useLeaveGuard, useUnsavedChanges } from './unsaved';

afterEach(() => vi.unstubAllGlobals());

function Editor() {
  const [dirty, setDirty] = useState(false);
  useUnsavedChanges('editor', dirty);
  return (
    <>
      <h1>Editor</h1>
      <button type="button" onClick={() => setDirty(true)}>
        Type something
      </button>
    </>
  );
}

function Shell() {
  useLeaveGuard();
  return (
    <>
      <Link to="/other">Elsewhere</Link>
      <Routes>
        <Route path="/" element={<Editor />} />
        <Route path="/other" element={<h1>Elsewhere page</h1>} />
      </Routes>
    </>
  );
}

it('asks before leaving a page with unsaved changes through any in-app link', async () => {
  const confirm = vi.fn(() => false);
  vi.stubGlobal('confirm', confirm);
  render(
    <MemoryRouter>
      <Shell />
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Type something' }));
  await user.click(screen.getByRole('link', { name: 'Elsewhere' }));
  expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/unsaved changes/));
  expect(screen.getByRole('heading', { name: 'Editor' })).toBeInTheDocument(); // stayed
  confirm.mockReturnValue(true);
  await user.click(screen.getByRole('link', { name: 'Elsewhere' }));
  expect(await screen.findByRole('heading', { name: 'Elsewhere page' })).toBeInTheDocument();
});

it('leaves without asking when nothing is unsaved', async () => {
  const confirm = vi.fn(() => false);
  vi.stubGlobal('confirm', confirm);
  render(
    <MemoryRouter>
      <Shell />
    </MemoryRouter>,
  );
  await userEvent.setup().click(screen.getByRole('link', { name: 'Elsewhere' }));
  expect(await screen.findByRole('heading', { name: 'Elsewhere page' })).toBeInTheDocument();
  expect(confirm).not.toHaveBeenCalled();
});

it('shows a loading bar while a request takes longer than a moment, but not for polls', async () => {
  vi.useFakeTimers();
  try {
    let answer: (r: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => (answer = resolve))),
    );
    render(<LoadingBar />);
    const status = screen.getByRole('status');
    const background = api.get('notifications/unread-count', undefined, undefined, true);
    await act(async () => vi.advanceTimersByTime(500));
    expect(status).toHaveTextContent('');
    answer(new Response('{}'));
    await act(async () => {
      await background;
    });
    const pending = api.get('dashboard');
    await act(async () => vi.advanceTimersByTime(100));
    expect(status).toHaveTextContent('');
    await act(async () => vi.advanceTimersByTime(300));
    expect(status).toHaveTextContent('Loading…');
    answer(new Response('{}'));
    await act(async () => {
      await pending;
    });
    await act(async () => vi.advanceTimersByTime(10));
    expect(status).toHaveTextContent('');
  } finally {
    vi.useRealTimers();
  }
});

it('background polls tell the server they are not user activity', async () => {
  const fetchMock = vi.fn(async () => new Response('{"unread":0}'));
  vi.stubGlobal('fetch', fetchMock);
  await api.get('notifications/unread-count', undefined, undefined, true);
  await api.get('me');
  const headers = (fetchMock.mock.calls as unknown as [string, RequestInit][]).map(
    ([, init]) => (init.headers as Record<string, string>)['X-Background'],
  );
  expect(headers).toEqual(['1', undefined]);
});
