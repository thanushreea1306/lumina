import type { ReactNode } from 'react';
import { TopBar } from './TopBar';
import { BottomNav } from './BottomNav';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        background: 'var(--lumina-bg)',
      }}
    >
      {/* Skip link for keyboard users */}
      <a
        href="#main-content"
        className="skip-link"
      >
        Skip to main content
      </a>

      <TopBar />

      <main
        id="main-content"
        role="main"
        style={{
          flex: 1,
          padding: 'var(--space-4) var(--space-4) calc(var(--space-4) + 3.5rem)',
          maxWidth: '1200px',
          width: '100%',
          margin: '0 auto',
        }}
      >
        {children}
      </main>

      <BottomNav />
    </div>
  );
}
