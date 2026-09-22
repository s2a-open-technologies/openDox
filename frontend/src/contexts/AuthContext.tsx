/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
  SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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

import { createContext, useState, useEffect, useContext, ReactNode } from 'react';
import { BASE_PATH } from '../api';

// Typen definieren
type User = {
  id: number;
  name: string;
  is_active: boolean;
  authenticated: boolean;
  role: 'admin' | 'moderator' | 'demo_viewer' | 'user';
  disclaimer_accepted_at?: string | null;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (name: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  acceptDisclaimer: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

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

  // Authentifizierten Fetch mit Token und CSRF
  const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const token = localStorage.getItem("access_token");
    const csrfToken = getCookie("csrf_access_token");
    const headers = {
      ...options.headers,
      "X-CSRF-TOKEN": csrfToken,
      Authorization: token ? `Bearer ${token}` : "",
    };
    return fetch(url, { ...options, headers, credentials: "include" });
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
        });
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
        return false;
      }

      const data = await res.json();
      if (!data.access_token) {
        console.error("No token received");
        return false;
      }

      localStorage.setItem("access_token", data.access_token);
      await fetchUser();
      return true;
    } catch (error) {
      console.error("Login error:", error);
      return false;
    } finally {
      setIsLoading(false);
    }
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
      localStorage.removeItem("access_token");
      localStorage.removeItem("currentSession");
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
    logout,
    authFetch,
    acceptDisclaimer,
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
