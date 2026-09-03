/* ============================================================
   LUMINA Case History
   ============================================================
   The backend has list_sessions() in db.py but it is NOT
   exposed via a router endpoint. The honest state is:
   "Case history is not available yet."
   ============================================================ */

import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SectionHeader } from '@/components/SectionHeader';
import { EmptyState } from '@/components/EmptyState';

export function HistoryPage() {
  const navigate = useNavigate();

  return (
    <div className="animate-fade-in">
      <SectionHeader
        number={5}
        title="Case History"
        subtitle="Past safety sessions and outcomes"
      />

      <Card style={{ marginBottom: 'var(--space-6)' }}>
        <EmptyState
          title="No History Available"
          description="Case history is not available yet. The backend session listing endpoint has not been implemented. When available, completed sessions will appear here with their safety decisions, evidence summaries, and outcomes."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
      </Card>

      <Card elevated style={{ borderLeft: '3px solid var(--lumina-system)' }}>
        <div style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--lumina-system)',
          marginBottom: 'var(--space-2)',
        }}>
          What Will Be Here
        </div>
        <p style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--lumina-text-muted)',
          lineHeight: 'var(--leading-relaxed)',
        }}>
          When the backend exposes a session listing endpoint, this page will show:
          a chronological list of your safety sessions, their safety states at completion,
          evidence counts, outcomes, and timestamps. Each entry will be a real record
          from the backend — never fabricated data.
        </p>
      </Card>

      <div style={{ marginTop: 'var(--space-6)' }}>
        <Button variant="secondary" onClick={() => navigate('/home')}>
          Return Home
        </Button>
      </div>
    </div>
  );
}
