import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  BrainCircuit,
  Database,
  CalendarDays,
  Sparkles,
  Sun,
  Moon,
  Search,
  Bell,
  Activity,
  ChevronRight,
  Menu,
  LogOut,
} from 'lucide-react';
import PortfolioOverview from './pages/PortfolioOverview';
import CategoryIntelligence from './pages/CategoryIntelligence';
import DataManagement from './pages/DataManagement';
import FestivalIntelligence from './pages/FestivalIntelligence';
import { API_BASE_URL, healthCheck } from './api/client';
import { useAuth } from './context/AuthContext';

const tabs = [
  { id: 'portfolio', label: 'Dashboard', sub: 'Portfolio Overview', icon: LayoutDashboard },
  { id: 'intelligence', label: 'Intelligence', sub: 'Category Analytics', icon: BrainCircuit },
  { id: 'data', label: 'Data Hub', sub: 'Data Management', icon: Database },
  { id: 'festival', label: 'Festivals', sub: 'Festival Intelligence', icon: CalendarDays },
];

const getInitialTheme = () => {
  const persisted = localStorage.getItem('marketpulse-theme');
  if (persisted === 'light' || persisted === 'dark') return persisted;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const getInitialTab = () => {
  const params = new URLSearchParams(window.location.search);
  const requestedTab = params.get('tab');
  return tabs.some((tab) => tab.id === requestedTab) ? requestedTab : 'portfolio';
};

const App = () => {
  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [backendReachable, setBackendReachable] = useState(true);
  const [connectionChecked, setConnectionChecked] = useState(false);
  const [theme, setTheme] = useState(getInitialTheme);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Handle fallback: if the popup couldn't close and redirected here with shopify params, clean the URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('shopify')) {
      // Remove shopify params from the URL so they don't persist on refresh
      params.delete('shopify');
      params.delete('shop');
      params.delete('message');
      params.delete('reason');
      const clean = params.toString();
      window.history.replaceState({}, '', clean ? `?${clean}` : window.location.pathname);
    }
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('marketpulse-theme', theme);
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    const runHealthCheck = async () => {
      try {
        await healthCheck();
        if (!cancelled) setBackendReachable(true);
      } catch {
        if (!cancelled) setBackendReachable(false);
      } finally {
        if (!cancelled) setConnectionChecked(true);
      }
    };

    runHealthCheck();
    const intervalId = window.setInterval(runHealthCheck, 15000);
    window.addEventListener('focus', runHealthCheck);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', runHealthCheck);
    };
  }, []);

  const renderPage = () => {
    switch (activeTab) {
      case 'portfolio': return <PortfolioOverview />;
      case 'intelligence': return <CategoryIntelligence />;
      case 'data': return <DataManagement />;
      case 'festival': return <FestivalIntelligence />;
      default: return null;
    }
  };

  const activeTabMeta = useMemo(() => tabs.find((tab) => tab.id === activeTab), [activeTab]);

  return (
    <div className="app-shell theme-transition">
      <div className="shell-grid">
        <aside className="side-rail px-5 py-6 text-white">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/20 font-bold">MP</div>
            <div>
              <p className="text-xs tracking-[0.16em] text-white/80">MARKETPULSE</p>
              <h1 className="text-lg font-bold leading-tight">Analytics AI</h1>
            </div>
          </div>

          <div className="mb-6 h-px bg-white/30" />

          <nav className="space-y-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`group w-full rounded-xl px-3 py-3 text-left transition-all cursor-pointer focus-visible:outline-white/80 ${
                    isActive
                      ? 'bg-black/30 ring-1 ring-white/35 shadow-[0_14px_28px_rgba(10,6,26,0.38)]'
                      : 'hover:bg-black/18'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon size={16} className={isActive ? 'text-white' : 'text-white/75 group-hover:text-white'} />
                    <div>
                      <p className="text-sm font-semibold leading-tight">{tab.label}</p>
                      <p className="text-[11px] text-white/78">{tab.sub}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="absolute bottom-6 left-5 right-5 space-y-2">
            {user && (
              <div className="rounded-2xl bg-black/28 p-3 ring-1 ring-white/28 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
                <p className="text-[10px] uppercase tracking-[0.18em] text-white/80">Signed in</p>
                <p className="mt-1 text-sm font-semibold truncate">{user.email}</p>
                <p className="mt-0.5 text-xs text-white/78 capitalize">{user.role}</p>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <LogOut size={14} />
              Logout
            </button>
          </div>
        </aside>

        <section className="main-panel min-h-[calc(100vh-40px)]">
          <header className="top-command mb-4 px-4 py-3 sm:px-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <button
                  onClick={() => setMobileNavOpen((v) => !v)}
                  className="rounded-lg border border-[var(--border)] bg-[var(--panel)] p-2 text-[var(--text-2)] lg:hidden"
                >
                  <Menu size={15} />
                </button>
                <div className="hidden md:flex items-center gap-2 rounded-full bg-[#0b1220] text-white px-3 py-1.5">
                  <Sparkles size={14} className="text-sky-300" />
                  <span className="text-xs font-semibold">MarketPulse Workspace</span>
                  <ChevronRight size={12} className="text-white/60" />
                </div>
                <h2 className="text-primary font-[var(--font-display)] text-xl font-semibold truncate">{activeTabMeta?.sub}</h2>
              </div>

              <div className="flex items-center gap-2">
                <button className="hidden sm:flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--panel)] text-[var(--text-2)] hover:text-[var(--text-1)]">
                  <Search size={15} />
                </button>
                <button className="hidden sm:flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--panel)] text-[var(--text-2)] hover:text-[var(--text-1)]">
                  <Bell size={15} />
                </button>

                <button
                  onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
                  className="relative h-10 w-[82px] rounded-full border border-[var(--border)] bg-[var(--panel-soft)] p-1 cursor-pointer"
                  aria-label="Toggle theme"
                >
                  <span className={`absolute top-1 h-8 w-8 rounded-full bg-gradient-to-br from-[var(--brand-1)] to-[var(--brand-2)] text-white shadow-md flex items-center justify-center transition-all duration-300 ${theme === 'dark' ? 'left-[42px]' : 'left-1'}`}>
                    {theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
                  </span>
                </button>

                {connectionChecked && (
                  <div className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${backendReachable ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-500' : 'border-red-500/30 bg-red-500/10 text-red-500'}`}>
                    <span className="inline-flex items-center gap-1.5"><Activity size={12} />{backendReachable ? 'Live' : 'Offline'}</span>
                  </div>
                )}
              </div>
            </div>

            {connectionChecked && !backendReachable && (
              <div className="mt-3 rounded-xl border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-500">
                Unable to reach backend.
                {' '}
                <span className="font-mono">
                  {API_BASE_URL ? `VITE_API_BASE_URL=${API_BASE_URL}` : 'Using local relative API paths'}
                </span>
              </div>
            )}

            {mobileNavOpen && (
              <div className="mt-3 grid grid-cols-1 gap-2 lg:hidden">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id);
                        setMobileNavOpen(false);
                      }}
                      className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${isActive ? 'border-sky-500/40 bg-sky-500/10 text-primary' : 'border-[var(--border)] bg-[var(--panel)] text-[var(--text-2)]'}`}
                    >
                      <Icon size={14} />
                      {tab.sub}
                    </button>
                  );
                })}
              </div>
            )}
          </header>

          <main key={activeTab} className="animate-fade-in-up px-1 pb-4 sm:px-2">
            {renderPage()}
          </main>
        </section>
      </div>
    </div>
  );
};

export default App;


