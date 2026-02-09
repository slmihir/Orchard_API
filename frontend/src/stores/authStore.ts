import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useEffect, useState } from 'react';

export interface RoleInfo {
  id: string;
  name: string;
  display_name: string;
  permissions: Record<string, boolean>;
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
  org_id: string | null;
  role_id: string | null;
  role: RoleInfo | null;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  _hasHydrated: boolean;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  setHasHydrated: (state: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      _hasHydrated: false,

      setAuth: (user: User, token: string) => {
        set({
          user,
          token,
          isAuthenticated: true,
        });
      },

      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
      },

      setHasHydrated: (state: boolean) => {
        set({ _hasHydrated: state });
      },
    }),
    {
      name: 'autoflow-auth',
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

export const getToken = () => useAuthStore.getState().token;

export const hasPermission = (permission: string): boolean => {
  const user = useAuthStore.getState().user;
  return user?.role?.permissions?.[permission] ?? false;
};

export const useHasPermission = (permission: string): boolean => {
  const user = useAuthStore((state) => state.user);
  return user?.role?.permissions?.[permission] ?? false;
};

export const useHasHydrated = () => {
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      setHasHydrated(true);
    });

    if (useAuthStore.persist.hasHydrated()) {
      setHasHydrated(true);
    }

    return () => unsub();
  }, []);

  return hasHydrated;
};
