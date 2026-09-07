/* ============================================================
   LUMINA Navigation Tests
   ============================================================
   Primary navigation reachability and active-state correctness:
   Home / Incident / Evidence / History. The legacy Session item
   must not appear in the primary nav.
   ============================================================ */

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { BottomNav } from '@/components/BottomNav';
import { TopBar } from '@/components/TopBar';

const NAV_PATHS = ['/home', '/incident', '/incident/new', '/evidence', '/history'];

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/home" element={<span>HOME-PAGE</span>} />
        <Route path="/incident" element={<span>INCIDENT-PAGE</span>} />
        <Route path="/incident/new" element={<span>INCIDENT-NEW-PAGE</span>} />
        <Route path="/evidence" element={<span>EVIDENCE-PAGE</span>} />
        <Route path="/history" element={<span>HISTORY-PAGE</span>} />
      </Routes>
      <BottomNav />
    </MemoryRouter>,
  );
}

describe('BottomNav - Reachable destinations', () => {
  it('navigates to Home', () => {
    renderAt('/history');
    fireEvent.click(screen.getByRole('button', { name: /home/i }));
    expect(screen.getByText('HOME-PAGE')).toBeInTheDocument();
  });

  it('navigates to Incident from the primary nav', () => {
    renderAt('/home');
    fireEvent.click(screen.getByRole('button', { name: /incident/i }));
    expect(screen.getByText('INCIDENT-PAGE')).toBeInTheDocument();
  });

  it('navigates to Evidence', () => {
    renderAt('/home');
    fireEvent.click(screen.getByRole('button', { name: /evidence/i }));
    expect(screen.getByText('EVIDENCE-PAGE')).toBeInTheDocument();
  });

  it('navigates to History', () => {
    renderAt('/home');
    fireEvent.click(screen.getByRole('button', { name: /history/i }));
    expect(screen.getByText('HISTORY-PAGE')).toBeInTheDocument();
  });
});

describe('BottomNav - Active state', () => {
  it.each(NAV_PATHS)('marks the current section active at %s', (path) => {
    renderAt(path);
    const activeButtons = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-current') === 'page');
    expect(activeButtons).toHaveLength(1);
  });

  it('marks Incident as active on both /incident and /incident/new', () => {
    renderAt('/incident/new');
    const active = screen.getByRole('button', { name: /incident/i });
    expect(active).toHaveAttribute('aria-current', 'page');
  });

  it('does not expose a Session item in the primary nav', () => {
    renderAt('/home');
    expect(screen.queryByRole('button', { name: /session/i })).not.toBeInTheDocument();
  });
});

describe('TopBar - Active state', () => {
  function renderTopBarAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/settings" element={<span>SETTINGS-PAGE</span>} />
          <Route path="/home" element={<span>HOME-PAGE</span>} />
        </Routes>
        <TopBar />
      </MemoryRouter>,
    );
  }

  it('marks Settings active when on /settings', () => {
    renderTopBarAt('/settings');
    const settings = screen.getByRole('button', { name: /settings/i });
    expect(settings).toHaveAttribute('aria-current', 'page');
  });

  it('does not mark Settings active on other protected pages', () => {
    renderTopBarAt('/home');
    const settings = screen.getByRole('button', { name: /settings/i });
    expect(settings).not.toHaveAttribute('aria-current');
  });
});