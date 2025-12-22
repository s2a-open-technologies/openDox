import { createContext, useContext, useState, useEffect, ReactNode } from "react";

// Typen definieren
type User = {
  id: number;
  name: string;
  is_active: boolean;
  authenticated: boolean;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (name: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
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
        if (res.ok) {
          setUser({
            id: data.id,
            name: data.name,
            is_active: data.is_active,
            authenticated: true,
          });
          setIsAuthenticated(true);
        } else {
          setUser(null);
          setIsAuthenticated(false);
        }
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (e) {
      console.error("Failed to fetch user: ", e);
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
      const res = await authFetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, password }),  // <-- Feldname anpassen
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
    } catch (e) {
      console.error("Login error:", e);
      setIsLoading(false);
      return false;
    }
  };

  // Logout-Funktion
  const logout = async (): Promise<void> => {
    try {
      const token = localStorage.getItem("access_token");
      if (token) {
        await authFetch("/api/v1/auth/logout", {
          method: "POST",
          credentials: "include",
        });
      }
    } catch (e) {
      console.warn("Logout failed", e);
    } finally {
      localStorage.removeItem("access_token");
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  // Initialen User laden
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      fetchUser();
    } else {
      setIsLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        login,
        logout,
        authFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// Custom Hook für den Auth-Kontext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
