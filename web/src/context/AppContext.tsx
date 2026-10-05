import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api/client';
import type { GumroadAccount } from '../api/types';
import { useAuth } from '../auth/AuthContext';

export type Theme = 'light' | 'dark';
export const ALL_ACCOUNTS = 'all';

interface AppContextValue {
  theme: Theme;
  toggleTheme: () => void;
  accounts: GumroadAccount[];
  accountsLoading: boolean;
  selectedAccountId: string;
  setSelectedAccountId: (id: string) => void;
  refreshAccounts: () => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

function initialTheme(): Theme {
  const saved = localStorage.getItem('ga_theme');
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [accounts, setAccounts] = useState<GumroadAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState<string>(
    () => localStorage.getItem('ga_account') ?? ALL_ACCOUNTS,
  );

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('ga_theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  const refreshAccounts = useCallback(async () => {
    if (!user) {
      setAccounts([]);
      return;
    }
    setAccountsLoading(true);
    try {
      const list = await api.listAccounts();
      setAccounts(list);
      setSelectedAccountId((prev) => {
        if (prev !== ALL_ACCOUNTS && !list.some((a) => a.id === prev)) {
          localStorage.setItem('ga_account', ALL_ACCOUNTS);
          return ALL_ACCOUNTS;
        }
        return prev;
      });
    } catch {
      /* header shows error-free; pages surface their own errors */
    } finally {
      setAccountsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refreshAccounts();
  }, [refreshAccounts]);

  const setSelected = useCallback((id: string) => {
    setSelectedAccountId(id);
    localStorage.setItem('ga_account', id);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      toggleTheme,
      accounts,
      accountsLoading,
      selectedAccountId,
      setSelectedAccountId: setSelected,
      refreshAccounts,
    }),
    [theme, toggleTheme, accounts, accountsLoading, selectedAccountId, setSelected, refreshAccounts],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}

/** Query fragment for account-scoped endpoints: omit for "All Accounts". */
export function accountQuery(selectedAccountId: string): { account_id?: string } {
  return selectedAccountId === ALL_ACCOUNTS ? {} : { account_id: selectedAccountId };
}
