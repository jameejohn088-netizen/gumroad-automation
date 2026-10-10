import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ALL_ACCOUNTS, useApp } from '../context/AppContext';
import { Button, Select } from './ui';

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/accounts', label: 'Gumroad Accounts' },
  { to: '/products', label: 'Products' },
  { to: '/sales', label: 'Sales' },
  { to: '/customers', label: 'Customers' },
  { to: '/subscribers', label: 'Subscribers' },
  { to: '/licenses', label: 'Licenses' },
  { to: '/memberships', label: 'Memberships' },
  { to: '/automations', label: 'Automations' },
  { to: '/scheduler', label: 'Scheduler' },
  { to: '/notifications', label: 'Notifications' },
  { to: '/logs', label: 'Logs' },
  { to: '/diagnostics', label: 'Diagnostics' },
  { to: '/settings', label: 'Settings' },
];

function navClass({ isActive }: { isActive: boolean }) {
  return `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200'
      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
  }`;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme, accounts, accountsLoading, selectedAccountId, setSelectedAccountId } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    api
      .notifications()
      .then((list) => {
        if (!cancelled) setUnread(list.filter((n) => !n.read).length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  const onLogout = async () => {
    await logout();
  };

  return (
    <div className="flex min-h-full">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900 md:block">
        <nav className="space-y-1" aria-label="Main navigation">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur dark:border-gray-800 dark:bg-gray-900/95">
          <div className="flex items-center gap-2 px-4 py-3">
            <button
              className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800 md:hidden"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
            <Link to="/" className="text-lg font-bold text-gray-900 dark:text-white">
              Gumroad<span className="text-blue-600"> Automation</span>
            </Link>

            <div className="ml-auto flex items-center gap-2">
              <label htmlFor="account-selector" className="sr-only">
                Select Gumroad account
              </label>
              <Select
                id="account-selector"
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                disabled={accountsLoading}
                className="w-auto min-w-36"
                aria-label="Select Gumroad account"
              >
                <option value={ALL_ACCOUNTS}>All Accounts</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
              <button
                onClick={toggleTheme}
                className="rounded-lg p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
              >
                {theme === 'dark' ? (
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm0 14a6 6 0 110-12 6 6 0 010 12z" />
                    <path d="M10 0v3M10 17v3M0 10h3M17 10h3M2.9 2.9l2.1 2.1M15 15l2.1 2.1M17.1 2.9L15 5M5 15l-2.1 2.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path d="M17.5 13.5A7.5 7.5 0 016.5 2.5a7.5 7.5 0 1011 11z" />
                  </svg>
                )}
              </button>
              <button
                onClick={() => navigate('/notifications')}
                className="relative rounded-lg p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
                title="Notifications"
              >
                <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path d="M10 2a6 6 0 00-6 6v3.5l-1.5 3h15L16 11.5V8a6 6 0 00-6-6zm-2.5 16a2.5 2.5 0 005 0h-5z" />
                </svg>
                {unread > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white">
                    {unread}
                  </span>
                )}
              </button>
              <div className="hidden items-center gap-2 sm:flex">
                <span className="max-w-40 truncate text-sm text-gray-600 dark:text-gray-300" title={user?.email}>
                  {user?.name || user?.email}
                </span>
                <Button variant="ghost" onClick={onLogout}>
                  Logout
                </Button>
              </div>
            </div>
          </div>

          {/* Mobile nav drawer */}
          {menuOpen && (
            <nav className="border-t border-gray-200 p-3 dark:border-gray-800 md:hidden" aria-label="Mobile navigation">
              <div className="grid grid-cols-2 gap-1">
                {NAV.map((item) => (
                  <NavLink key={item.to} to={item.to} end={item.end} className={navClass} onClick={() => setMenuOpen(false)}>
                    {item.label}
                  </NavLink>
                ))}
              </div>
              <Button variant="ghost" className="mt-2 w-full sm:hidden" onClick={onLogout}>
                Logout ({user?.email})
              </Button>
            </nav>
          )}
        </header>

        <main className="flex-1 px-4 py-6 md:px-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
