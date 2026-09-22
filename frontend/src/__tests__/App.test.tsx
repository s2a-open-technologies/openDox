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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import App from "@/App";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: vi.fn(),
}));

vi.mock("@/pages/Login", () => ({
  default: () => <div data-testid="login-page">Login Page</div>,
}));

vi.mock("@/pages/Dashboard", () => ({
  default: () => <div data-testid="dashboard-page">Dashboard Page</div>,
}));

vi.mock("@/pages/NotFound", () => ({
  default: () => <div data-testid="notfound-page">Not Found Page</div>,
}));

vi.mock("sonner", () => ({
  Toaster: () => null,
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

type AuthState = {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: { disclaimer_accepted_at: string | null } | null;
};

function mockAuth({ isAuthenticated, isLoading, user }: AuthState) {
  mockedUseAuth.mockReturnValue({
    user: user as never,
    isLoading,
    isAuthenticated,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch: vi.fn(),
    acceptDisclaimer: vi.fn(),
  });
}

describe("App routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("shows a loading indicator while auth state is resolving", () => {
    window.history.pushState({}, "", "/dashboard");
    mockAuth({ isAuthenticated: false, isLoading: true, user: null });

    render(<App />);

    expect(screen.getByText("Lädt...")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-page")).not.toBeInTheDocument();
  });

  it("redirects unauthenticated users from a protected route to /login", () => {
    window.history.pushState({}, "", "/dashboard");
    mockAuth({ isAuthenticated: false, isLoading: false, user: null });

    render(<App />);

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-page")).not.toBeInTheDocument();
  });

  it("shows the DisclaimerGate for authenticated users who have not accepted it", () => {
    window.history.pushState({}, "", "/dashboard");
    mockAuth({
      isAuthenticated: true,
      isLoading: false,
      user: { disclaimer_accepted_at: null },
    });

    render(<App />);

    expect(screen.getByText("Kein Medizinprodukt")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-page")).not.toBeInTheDocument();
  });

  it("renders the protected page for authenticated users who accepted the disclaimer", () => {
    window.history.pushState({}, "", "/dashboard");
    mockAuth({
      isAuthenticated: true,
      isLoading: false,
      user: { disclaimer_accepted_at: "2026-01-01T00:00:00Z" },
    });

    render(<App />);

    expect(screen.getByTestId("dashboard-page")).toBeInTheDocument();
    expect(screen.queryByText("Kein Medizinprodukt")).not.toBeInTheDocument();
  });

  it("redirects the root path to /dashboard", () => {
    window.history.pushState({}, "", "/");
    mockAuth({
      isAuthenticated: true,
      isLoading: false,
      user: { disclaimer_accepted_at: "2026-01-01T00:00:00Z" },
    });

    render(<App />);

    expect(screen.getByTestId("dashboard-page")).toBeInTheDocument();
  });

  it("renders /login directly without gating on auth state", () => {
    window.history.pushState({}, "", "/login");
    mockAuth({ isAuthenticated: false, isLoading: false, user: null });

    render(<App />);

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });

  it("renders the NotFound page for unknown routes", () => {
    window.history.pushState({}, "", "/some/unknown/route");
    mockAuth({ isAuthenticated: false, isLoading: false, user: null });

    render(<App />);

    expect(screen.getByTestId("notfound-page")).toBeInTheDocument();
  });
});
