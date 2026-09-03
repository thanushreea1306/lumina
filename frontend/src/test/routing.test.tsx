import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WelcomePage } from '@/app/WelcomePage';
import { ConsentPage } from '@/app/ConsentPage';
import { HomePage } from '@/app/HomePage';
import { SessionPage } from '@/app/SessionPage';
import { EvidencePage } from '@/app/EvidencePage';
import { HistoryPage } from '@/app/HistoryPage';
import { SettingsPage } from '@/app/SettingsPage';
import { TrustedContactPage } from '@/app/TrustedContactPage';

function renderAtRoute(path: string, element: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={path} element={element} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Routing - Page renders at correct path', () => {
  it('WelcomePage renders', () => {
    renderAtRoute('/', <WelcomePage />);
    expect(screen.getByText('LUMINA')).toBeInTheDocument();
    expect(screen.getByText(/digital forensics/i)).toBeInTheDocument();
  });

  it('ConsentPage renders', () => {
    renderAtRoute('/consent', <ConsentPage />);
    expect(screen.getByText(/data & privacy/i)).toBeInTheDocument();
  });

  it('HomePage renders loading state initially', () => {
    renderAtRoute('/home', <HomePage />);
    const elements = screen.getAllByText(/connecting to lumina/i);
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('SessionPage renders creation view', () => {
    renderAtRoute('/session', <SessionPage />);
    // SessionPage now shows creation view when no session is active
    expect(screen.getByText(/begin a safety session/i)).toBeInTheDocument();
  });

  it('EvidencePage renders', () => {
    renderAtRoute('/evidence', <EvidencePage />);
    expect(screen.getByText(/evidence board/i)).toBeInTheDocument();
  });

  it('HistoryPage renders', () => {
    renderAtRoute('/history', <HistoryPage />);
    expect(screen.getByText(/session history/i)).toBeInTheDocument();
  });

  it('SettingsPage renders', () => {
    renderAtRoute('/settings', <SettingsPage />);
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
  });

  it('TrustedContactPage renders', () => {
    renderAtRoute('/trusted-contact', <TrustedContactPage />);
    // Use heading role to disambiguate from capability banner text
    expect(screen.getByRole('heading', { name: 'Trusted Contact' })).toBeInTheDocument();
    expect(screen.getByText(/not yet fully configured/i)).toBeInTheDocument();
  });
});
