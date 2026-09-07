import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Button } from '@/components/Button';
import { StatusBadge } from '@/components/StatusBadge';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { ErrorState } from '@/components/ErrorState';
import { UnavailableState } from '@/components/UnavailableState';
import { TopBar } from '@/components/TopBar';
import { BottomNav } from '@/components/BottomNav';
import { SectionHeader } from '@/components/SectionHeader';
import { CaseID } from '@/components/CaseID';
import { Divider } from '@/components/Divider';

function renderWithRouter(ui: React.ReactNode) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('can be disabled', () => {
    render(<Button disabled>Click me</Button>);
    const button = screen.getByRole('button', { name: /click me/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-disabled', 'true');
  });

  it('calls onClick when clicked', async () => {
    let clicked = false;
    render(<Button onClick={() => { clicked = true; }}>Click me</Button>);
    screen.getByRole('button', { name: /click me/i }).click();
    expect(clicked).toBe(true);
  });
});

describe('StatusBadge', () => {
  it('renders safety state label', () => {
    render(<StatusBadge state="CLEAR" />);
    expect(screen.getByText('Clear')).toBeInTheDocument();
  });

  it('has role="status"', () => {
    render(<StatusBadge state="WATCH" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows all safety states', () => {
    const states = ['CLEAR', 'WATCH', 'PAUSE', 'VERIFY', 'PROTECT', 'RECOVERY'] as const;
    for (const state of states) {
      const { unmount } = render(<StatusBadge state={state} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
      unmount();
    }
  });
});

describe('Card', () => {
  it('renders children', () => {
    render(<Card><p>Card content</p></Card>);
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('has role="region"', () => {
    render(<Card>Content</Card>);
    expect(screen.getByRole('region')).toBeInTheDocument();
  });
});

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No data" description="Nothing to show" />);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText('Nothing to show')).toBeInTheDocument();
  });

  it('has role="status"', () => {
    render(<EmptyState title="Empty" description="No items" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('LoadingState', () => {
  it('renders loading message', () => {
    render(<LoadingState message="Loading data" />);
    // Uses getAllByText because sr-only span and visible text both contain the message
    const elements = screen.getAllByText('Loading data');
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('has role="status" and aria-live', () => {
    render(<LoadingState />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
  });
});

describe('ErrorState', () => {
  it('renders error title and message', () => {
    render(<ErrorState title="Error" message="Something went wrong" />);
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('has role="alert"', () => {
    render(<ErrorState title="Error" message="Failed" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows retry button when onRetry provided', () => {
    render(<ErrorState title="Error" message="Failed" onRetry={() => {}} />);
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });
});

describe('UnavailableState', () => {
  it('renders default message', () => {
    render(<UnavailableState />);
    expect(screen.getByText('Backend Unavailable')).toBeInTheDocument();
  });

  it('has role="alert" and aria-live="assertive"', () => {
    render(<UnavailableState />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
  });
});

describe('TopBar', () => {
  it('renders LUMINA wordmark', () => {
    renderWithRouter(<TopBar />);
    expect(screen.getByText('LUMINA')).toBeInTheDocument();
  });

  it('has banner role', () => {
    renderWithRouter(<TopBar />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});

describe('BottomNav', () => {
  it('renders Home, Incident, Evidence, and History navigation items', () => {
    renderWithRouter(<BottomNav />);
    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /incident/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /evidence/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /history/i })).toBeInTheDocument();
  });

  it('does not expose the legacy Session item in the primary nav', () => {
    renderWithRouter(<BottomNav />);
    expect(screen.queryByRole('button', { name: /session/i })).not.toBeInTheDocument();
  });
});

describe('SectionHeader', () => {
  it('renders title', () => {
    render(<SectionHeader title="My Section" />);
    expect(screen.getByText('My Section')).toBeInTheDocument();
  });

  it('renders number when provided', () => {
    render(<SectionHeader number={3} title="Section" />);
    expect(screen.getByText('03')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<SectionHeader title="Section" subtitle="A subtitle" />);
    expect(screen.getByText('A subtitle')).toBeInTheDocument();
  });
});

describe('CaseID', () => {
  it('renders session ID', () => {
    render(<CaseID sessionId="abc123def456" />);
    expect(screen.getByRole('text', { name: /session abc123def456/i })).toBeInTheDocument();
  });
});

describe('Divider', () => {
  it('renders an hr element', () => {
    render(<Divider />);
    const hr = document.querySelector('hr');
    expect(hr).toBeInTheDocument();
    expect(hr).toHaveAttribute('aria-hidden', 'true');
  });
});
