import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Activity, ChevronRight, CircleCheck, FileText, FlaskConical, House, Layers3, LogIn, Mail, Menu, Settings as SettingsIcon, Share2, Sun, TriangleAlert, X, Zap } from 'lucide-react';
import { errorMessage, request, SESSION_EXPIRED } from './api';
import type { Role, Session } from './api';
import { Empty, PageTitle } from './components';
import { Events, EventDetails } from './Events';
import { Integrations } from './Integrations';
import { Audit, Settings, Simulation, SystemHealth } from './Operations';
import type { Theme } from './Operations';
import { Overview } from './Overview';
import { roleLabels } from './format';

const workspaceItems = [
  { id: 'overview', label: 'Overview', icon: House },
  { id: 'integrations', label: 'Integrations', icon: Layers3 },
  { id: 'events', label: 'Events', icon: Zap },
  { id: 'dead-letter', label: 'Dead Letter Queue', icon: Mail },
] as const;

const operationItems = [
  { id: 'incidents', label: 'Incidents', icon: TriangleAlert },
  { id: 'health', label: 'System Health', icon: Activity },
  { id: 'audit', label: 'Audit Logs', icon: FileText },
  { id: 'simulation', label: 'Failure Simulation', icon: FlaskConical },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
] as const;

const items = [...workspaceItems, ...operationItems];
type Item = typeof items[number];
type PageId = Item['id'];

function allowed(page: PageId, role: Role) {
  if (page === 'audit') return role === 'admin';
  if (page === 'simulation') return role !== 'viewer';
  return true;
}

function readRoute(hash: string) {
  const [path, query] = hash.replace(/^#\/?/, '').split('?', 2);
  const [section, id] = path.split('/');
  const item = items.find((entry) => entry.id === section) ?? workspaceItems[0];
  let detailId: string | undefined;
  try { detailId = id ? decodeURIComponent(id) : undefined; } catch { detailId = undefined; }
  return { item, id: detailId, filters: new URLSearchParams(query) };
}

function Brand() {
  return <div className="brand"><Share2 size={39} className="brand-mark" strokeWidth={1.8} aria-hidden="true" /><div><strong>SyncOps</strong><small>Integration operations</small></div></div>;
}

function ThemeSwitch({ theme, change }: { theme: Theme; change: () => void }) {
  return <button className="theme-switch" type="button" role="switch" aria-label="Dark theme" aria-checked={theme === 'dark'} onClick={change}><Sun size={20} aria-hidden="true" /><span className="switch-track" aria-hidden="true"><i /></span></button>;
}

function SignIn({ note, theme, changeTheme, authenticated }: { note: string; theme: Theme; changeTheme: () => void; authenticated: (session: Session) => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setError('');
    setBusy(true);
    try {
      authenticated(await request<Session>('/auth/login', undefined, { method: 'POST', body: JSON.stringify({ username: String(fields.get('username')).trim(), password: fields.get('password') }) }));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="sign-in-screen">
      <div className="sign-in-theme"><ThemeSwitch theme={theme} change={changeTheme} /></div>
      <section className="panel sign-in-card" aria-labelledby="sign-in-title">
        <Brand />
        <h1 id="sign-in-title">Sign in to SyncOps</h1>
        <p className="muted-text">Use the credentials configured for this workspace.</p>
        {note && <p className="notice" role="status">{note}</p>}
        <form className="form-stack" onSubmit={login}>
          <label className="field">Username<input name="username" required autoComplete="username" maxLength={64} /></label>
          <label className="field">Password<input name="password" required type="password" autoComplete="current-password" maxLength={256} /></label>
          {error && <p className="notice error" role="alert">{error}</p>}
          <button className="button primary" disabled={busy}><LogIn size={18} aria-hidden="true" />{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
      </section>
    </main>
  );
}

function Sidebar({ page, role, open, close }: { page: PageId; role: Role; open: boolean; close: () => void }) {
  const link = ({ id, label, icon: Icon }: Item) => (
    <a key={id} href={`#/${id}`} className="nav-item" aria-current={id === page ? 'page' : undefined} onClick={close}><Icon size={21} strokeWidth={1.8} aria-hidden="true" />{label}</a>
  );
  return (
    <aside className={`sidebar${open ? ' mobile-open' : ''}`} id="workspace-sidebar">
      <div className="sidebar-top"><a href="#/overview" onClick={close}><Brand /></a><button type="button" className="icon-button close-nav" onClick={close} aria-label="Close navigation"><X size={20} /></button></div>
      <nav aria-label="Workspace navigation">
        <div className="nav-group">{workspaceItems.map(link)}</div>
        <div className="nav-divider" />
        <div className="nav-group" aria-label="Operations"><h2>Operations</h2>{operationItems.filter(({ id }) => allowed(id, role)).map(link)}</div>
      </nav>
    </aside>
  );
}

function saveTheme(theme: Theme) {
  try { window.localStorage.setItem('syncops-theme', theme); } catch { /* Use the current tab preference. */ }
}

function initialTheme(): Theme {
  try { return window.localStorage.getItem('syncops-theme') === 'light' ? 'light' : 'dark'; } catch { return 'dark'; }
}

export function App() {
  const [session, setSession] = useState<Session>();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [hash, setHash] = useState(window.location.hash);
  const [menuOpen, setMenuOpen] = useState(false);
  const [note, setNote] = useState('');
  const [toast, setToast] = useState<{ message: string }>();
  const mainRef = useRef<HTMLElement>(null);
  const { item, id, filters } = readRoute(hash);

  useEffect(() => {
    function navigate() {
      setHash(window.location.hash);
      setMenuOpen(false);
      window.scrollTo(0, 0);
    }
    function expired() {
      setSession(undefined);
      setMenuOpen(false);
      setNote('Your session expired. Sign in to continue.');
    }
    window.addEventListener('hashchange', navigate);
    window.addEventListener(SESSION_EXPIRED, expired);
    return () => {
      window.removeEventListener('hashchange', navigate);
      window.removeEventListener(SESSION_EXPIRED, expired);
    };
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(undefined), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!menuOpen) return;
    const previousFocus = document.activeElement;
    document.querySelector<HTMLButtonElement>('.close-nav')?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false);
    }
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      if (previousFocus instanceof HTMLElement) previousFocus.focus();
    };
  }, [menuOpen]);

  function toggleTheme() { setTheme((current) => current === 'dark' ? 'light' : 'dark'); }
  function notify(message: string) { setToast({ message }); }

  async function signOut() {
    if (!session) return;
    try {
      await request<void>('/auth/logout', session.token, { method: 'POST' });
      setNote('You are signed out.');
    } catch {
      setNote('Signed out of this tab. The server session may remain active until it expires.');
    } finally {
      setSession(undefined);
      setToast(undefined);
      setMenuOpen(false);
    }
  }

  if (!session) return <SignIn theme={theme} changeTheme={toggleTheme} note={note} authenticated={(authenticated) => { setSession(authenticated); setNote(''); }} />;

  let content: ReactNode;
  if (!allowed(item.id, session.user.role)) {
    content = <><PageTitle title={item.label} description="This page is unavailable for your role." /><div className="panel"><Empty title="Access restricted"><a href="#/overview" className="text-link">Return to overview</a></Empty></div></>;
  } else switch (item.id) {
    case 'overview': content = <Overview session={session} />; break;
    case 'integrations': content = <Integrations session={session} id={id} notify={notify} />; break;
    case 'events': content = id ? <EventDetails session={session} id={id} notify={notify} /> : <Events session={session} mode="events" filters={filters} />; break;
    case 'dead-letter': content = <Events session={session} mode="dead-letter" filters={filters} />; break;
    case 'incidents': content = <Events session={session} mode="incidents" filters={filters} />; break;
    case 'health': content = <SystemHealth token={session.token} />; break;
    case 'audit': content = <Audit token={session.token} />; break;
    case 'simulation': content = <Simulation session={session} notify={notify} />; break;
    case 'settings': content = <Settings session={session} theme={theme} onTheme={setTheme} signOut={() => void signOut()} />; break;
  }

  return (
    <div className="workspace">
      <a href="#main" className="skip-link" onClick={(event) => { event.preventDefault(); mainRef.current?.focus(); }}>Skip to content</a>
      <Sidebar page={item.id} role={session.user.role} open={menuOpen} close={() => setMenuOpen(false)} />
      {menuOpen && <button type="button" tabIndex={-1} className="nav-scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <div className="workspace-main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button open-nav" aria-label="Open navigation" aria-expanded={menuOpen} aria-controls="workspace-sidebar" type="button" onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{item.label}</strong></div>
          </div>
          <div className="topbar-actions"><ThemeSwitch theme={theme} change={toggleTheme} /><span className="topbar-rule" /><a className="avatar" href="#/settings" aria-label={`Settings for ${session.user.username}, ${roleLabels[session.user.role]}`} title={session.user.username}>{session.user.username.slice(0, 2).toUpperCase()}</a></div>
        </header>
        <main className="workspace-content" id="main" tabIndex={-1} ref={mainRef}>
          <div key={hash || '#/overview'}>{content}</div>
        </main>
      </div>
      {toast && <div className="toast" role="status"><CircleCheck size={20} className="success" aria-hidden="true" /><span>{toast.message}</span><button type="button" className="icon-button" aria-label="Dismiss notification" onClick={() => setToast(undefined)}><X size={17} /></button></div>}
    </div>
  );
}
