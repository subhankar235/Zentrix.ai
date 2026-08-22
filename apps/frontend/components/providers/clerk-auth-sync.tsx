'use client';

import * as React from 'react';
import { useAuth, useUser } from '@clerk/nextjs';
import { setApiAuthTokenGetter } from '@/lib/api/client';
import { useAuthStore } from '@/stores/use-auth-store';

export function ClerkAuthSync({ children }: { children?: React.ReactNode }) {
  const { getToken, isSignedIn } = useAuth();
  const { user } = useUser();
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);

  // Connect Clerk's live token getter to the HTTP API client
  React.useEffect(() => {
    if (isSignedIn) {
      setApiAuthTokenGetter(async () => {
        try {
          return await getToken();
        } catch {
          return null;
        }
      });
    } else {
      setApiAuthTokenGetter(null);
    }
  }, [isSignedIn, getToken]);

  // Sync Clerk user profile into Zustand store
  React.useEffect(() => {
    if (isSignedIn && user) {
      setUser({
        id: user.id,
        email: user.primaryEmailAddress?.emailAddress || '',
        fullName: user.fullName || user.username || undefined,
        role: 'dba',
      });
    } else if (!isSignedIn) {
      logout();
    }
  }, [isSignedIn, user, setUser, logout]);

  return <>{children}</>;
}
