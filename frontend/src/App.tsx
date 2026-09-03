import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { WelcomePage } from '@/app/WelcomePage';
import { ConsentPage } from '@/app/ConsentPage';
import { HomePage } from '@/app/HomePage';
import { SessionPage } from '@/app/SessionPage';
import { EvidencePage } from '@/app/EvidencePage';
import { HistoryPage } from '@/app/HistoryPage';
import { SettingsPage } from '@/app/SettingsPage';
import { VerifyPage } from '@/app/VerifyPage';
import { PausePage } from '@/app/PausePage';
import { ProtectPage } from '@/app/ProtectPage';
import { TrustedContactPage } from '@/app/TrustedContactPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes (no shell) */}
        <Route path="/" element={<WelcomePage />} />
        <Route path="/welcome" element={<Navigate to="/" replace />} />
        <Route path="/consent" element={<ConsentPage />} />

        {/* Protected routes (with shell) */}
        <Route
          path="/home"
          element={
            <AppShell>
              <HomePage />
            </AppShell>
          }
        />
        <Route
          path="/session"
          element={
            <AppShell>
              <SessionPage />
            </AppShell>
          }
        />
        <Route
          path="/evidence"
          element={
            <AppShell>
              <EvidencePage />
            </AppShell>
          }
        />
        <Route
          path="/history"
          element={
            <AppShell>
              <HistoryPage />
            </AppShell>
          }
        />
        <Route
          path="/verify"
          element={
            <AppShell>
              <VerifyPage />
            </AppShell>
          }
        />
        <Route
          path="/pause"
          element={
            <AppShell>
              <PausePage />
            </AppShell>
          }
        />
        <Route
          path="/protect"
          element={
            <AppShell>
              <ProtectPage />
            </AppShell>
          }
        />
        <Route
          path="/trusted-contact"
          element={
            <AppShell>
              <TrustedContactPage />
            </AppShell>
          }
        />
        <Route
          path="/settings"
          element={
            <AppShell>
              <SettingsPage />
            </AppShell>
          }
        />

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
