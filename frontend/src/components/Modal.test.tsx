import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Modal from './Modal';

it('keeps keyboard focus inside a dialog in both directions', async () => {
  const user = userEvent.setup();
  render(
    <Modal title="Review report" onClose={() => undefined}>
      <label>
        Review note
        <input />
      </label>
      <button type="button">Finish review</button>
    </Modal>,
  );
  const first = screen.getByRole('button', { name: 'Close' });
  const last = screen.getByRole('button', { name: 'Finish review' });
  first.focus();
  await user.tab({ shift: true });
  expect(last).toHaveFocus();
  await user.tab();
  expect(first).toHaveFocus();
});

it('closes on Escape and restores the previous control when removed', async () => {
  const user = userEvent.setup();
  const trigger = document.createElement('button');
  trigger.textContent = 'Open review';
  document.body.append(trigger);
  trigger.focus();
  const onClose = vi.fn();
  const { unmount } = render(
    <Modal title="Review report" onClose={onClose}>
      <input aria-label="Review note" />
    </Modal>,
  );
  await user.keyboard('{Escape}');
  expect(onClose).toHaveBeenCalledOnce();
  unmount();
  expect(trigger).toHaveFocus();
  trigger.remove();
});
