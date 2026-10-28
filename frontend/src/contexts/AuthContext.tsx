/*
  openDox - Medical transcription platform
  Copyright (C) 2025  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
  SPDX-License-Identifier: AGPL-3.0-or-later

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

import { createContext, useState, useEffect, useContext, useRef, ReactNode } from 'react';
import { toast } from 'sonner';
import { BASE_PATH } from '../api';
import i18n, { applyUiLanguage, isSupportedLanguage, type UiLanguage } from '@/i18n';
import { clearActivity, markActivity } from '@/lib/sessionActivity';
import { apiErrorMessage } from '@/lib/apiError';

// Credentials were right but the server refuses the login (e.g. the account
// is locked); its message is meant for the user, unlike a plain failure.
export class LoginRefusedError extends Error {}

// Typen definieren
type User = {
  id: number;
  name: string;
  is_active: boolean;
  authenticated: boolean;
  role: 'admin' | 'moderator' | 'demo_viewer' | 'user';
  disclaimer_accepted_at?: string | null;
  ui_language?: string | null;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (name: string, password: string) => Promise<boolean>;
  loginWithTokens: (accessToken: string, refreshToken: string | null) => Promise<void>;
  logout: () => Promise<void>;
  expireSession: (reason: 'expired' | 'idle') => void;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  getFreshToken: () => Promise<string>;
  acceptDisclaimer: () => Promise<boolean>;
  updateUiLanguage: (code: UiLanguage) => Promise<boolean>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

type RefreshOutcome = 'ok' | 'rejected' | 'error';

// Renew a little before the access token runs out, so a WebSocket opened with
// it is not refused right at the edge.
const REFRESH_MARGIN_MS = 60_000;

// Expiry of a JWT in ms since the epoch; 0 if it cannot be read.
const tokenExpiry = (token: string): number => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
};

const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("currentSession");
  clearActivity();
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  // CSRF-Cookie extrahieren
  const getCookie = (name: string): string | undefined => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop()?.split(";").shift();
  };

  // One renewal at a time: parallel 401s wait for the same refresh instead of
  // each spending the (rotating) refresh token.
  const refreshInFlight = useRef<Promise<RefreshOutcome> | null>(null);

  // Swap the refresh token for a fresh token pair. The server also re-checks
  // LDAP/OIDC users here, so "rejected" means the session is really over;
  // "error" (server unreachable) leaves the tokens alone.
  const refreshAccessToken = (): Promise<RefreshOutcome> => {
    if (refreshInFlight.current) return refreshInFlight.current;
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return Promise.resolve('rejected');
    refreshInFlight.current = (async (): Promise<RefreshOutcome> => {
      try {
        // In the body, not the URL: URLs end up in proxy access logs.
        const res = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (res.status === 401) return 'rejected';
        if (!res.ok) return 'error';
        const data = await res.json();
        if (!data.access_token || !data.refresh_token) return 'error';
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        return 'ok';
      } catch (error) {
        console.error("Token refresh error:", error);
        return 'error';
      } finally {
        refreshInFlight.current = null;
      }
    })();
    return refreshInFlight.current;
  };

  // End the session on the client and send the user to the login page
  // (ProtectedRoute redirects as soon as isAuthenticated is false).
  const expireSession = (reason: 'expired' | 'idle'): void => {
    clearTokens();
    setUser(null);
    setIsAuthenticated(false);
    toast.info(i18n.t(reason === 'idle' ? 'login:idleLogout' : 'login:sessionExpired'));
  };

  const plainFetch = (url: string, options: RequestInit): Promise<Response> => {
    const token = localStorage.getItem("access_token");
    const csrfToken = getCookie("csrf_access_token");
    const headers = {
      ...options.headers,
      "X-CSRF-TOKEN": csrfToken,
      Authorization: token ? `Bearer ${token}` : "",
    };
    return fetch(url, { ...options, headers, credentials: "include" });
  };

  // Authentifizierten Fetch mit Token und CSRF. Ein abgelaufenes Access-Token
  // wird still erneuert und die Anfrage einmal wiederholt.
  const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const res = await plainFetch(url, options);
    if (res.status !== 401) return res;
    const outcome = await refreshAccessToken();
    if (outcome === 'ok') return plainFetch(url, options);
    if (outcome === 'rejected' && localStorage.getItem("access_token")) {
      expireSession('expired');
    }
    return res;
  };

  // Access token for connections that cannot retry on 401 (the recording
  // WebSocket): renewed first if it is about to run out.
  const getFreshToken = async (): Promise<string> => {
    const token = localStorage.getItem("access_token") || "";
    const expiry = token ? tokenExpiry(token) : 0;
    if (expiry && expiry - Date.now() < REFRESH_MARGIN_MS) {
      const outcome = await refreshAccessToken();
      if (outcome === 'rejected') {
        expireSession('expired');
        return "";
      }
    }
    return localStorage.getItem("access_token") || "";
  };

  // User-Daten vom Server abrufen
  const fetchUser = async (): Promise<void> => {
    try {
      const res = await authFetch("/api/v1/auth/me", {
        method: "GET",
      });
      if (res.ok) {
        const data = await res.json();
        setUser({
          id: data.id,
          name: data.name,
          is_active: data.is_active,
          authenticated: true,
          role: data.role,
          disclaimer_accepted_at: data.disclaimer_accepted_at ?? null,
          ui_language: data.ui_language ?? null,
        });
        // The stored per-user language wins over the pre-login fallback.
        if (isSupportedLanguage(data.ui_language)) {
          await applyUiLanguage(data.ui_language);
        }
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error("Error fetching user:", error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Login-Funktion
  const login = async (name: string, password: string): Promise<boolean> => {
    setIsLoading(true);

    try {
      // Authentifizierung NUR über Backend
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          password: password,
        }),
        credentials: "include",
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Login failed" }));
        console.error("Login error:", errorData);
        if (res.status === 403) {
          throw new LoginRefusedError(apiErrorMessage(errorData, i18n.t('login:failed')));
        }
        return false;
      }

      const data = await res.json();
      if (!data.access_token) {
        console.error("No token received");
        return false;
      }

      localStorage.setItem("access_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      markActivity();
      await fetchUser();
      return true;
    } catch (error) {
      if (error instanceof LoginRefusedError) throw error;
      console.error("Login error:", error);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  // Abschluss eines OIDC/SSO-Logins: die Tokens kommen aus der Redirect-URL
  // statt aus dem Passwort-Formular, danach gilt dieselbe Erneuerung.
  const loginWithTokens = async (accessToken: string, refreshToken: string | null): Promise<void> => {
    setIsLoading(true);
    localStorage.setItem("access_token", accessToken);
    if (refreshToken) localStorage.setItem("refresh_token", refreshToken);
    markActivity();
    await fetchUser();
  };

  // Logout-Funktion
  const logout = async (): Promise<void> => {
    try {
      // Versuche, sich vom Backend abzumelden
      await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      // Bereinige alle Tokens und Benutzerdaten
      clearTokens();
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  // Disclaimer-Akzeptanz an den Server melden und lokalen User-State aktualisieren
  const acceptDisclaimer = async (): Promise<boolean> => {
    try {
      const res = await authFetch("/api/v1/auth/accept-disclaimer", {
        method: "POST",
      });
      if (!res.ok) return false;
      const data = await res.json();
      setUser((prev) =>
        prev ? { ...prev, disclaimer_accepted_at: data.disclaimer_accepted_at } : prev
      );
      return true;
    } catch (error) {
      console.error("Error accepting disclaimer:", error);
      return false;
    }
  };

  // UI-Sprache serverseitig speichern, dann lokal anwenden
  const updateUiLanguage = async (code: UiLanguage): Promise<boolean> => {
    try {
      const res = await authFetch("/api/v1/settings/my-language/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui_language: code }),
      });
      if (!res.ok) return false;
      setUser((prev) => (prev ? { ...prev, ui_language: code } : prev));
      await applyUiLanguage(code);
      return true;
    } catch (error) {
      console.error("Error saving UI language:", error);
      return false;
    }
  };

  // Beim Laden des Kontexts versuchen, den Benutzerstatus wiederherzustellen
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      fetchUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  const value = {
    user,
    isLoading,
    isAuthenticated,
    login,
    loginWithTokens,
    logout,
    expireSession,
    authFetch,
    getFreshToken,
    acceptDisclaimer,
    updateUiLanguage,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
