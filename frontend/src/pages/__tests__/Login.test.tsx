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
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Login from "@/pages/Login";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

function renderLogin(login: ReturnType<typeof vi.fn>, initialEntries = ["/login"]) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login,
    logout: vi.fn(),
    authFetch: vi.fn(),
    acceptDisclaimer: vi.fn(),
  });
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Login />
    </MemoryRouter>
  );
}

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Default: OIDC status check resolves disabled, so it never interferes
    // with tests that don't care about SSO.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ enabled: false })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("renders the username/password form and submit button", () => {
    renderLogin(vi.fn());

    expect(screen.getByPlaceholderText("Username")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Passwort")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anmelden" })).toBeInTheDocument();
  });

  it("calls login with the entered credentials and shows a success toast", async () => {
    const login = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    renderLogin(login);

    await user.type(screen.getByPlaceholderText("Username"), "dr.mueller");
    await user.type(screen.getByPlaceholderText("Passwort"), "secret");
    await user.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("dr.mueller", "secret"));
    expect(toast.success).toHaveBeenCalledWith("Erfolgreich angemeldet");
  });

  it("shows an error toast when login resolves false", async () => {
    const login = vi.fn().mockResolvedValue(false);
    const user = userEvent.setup();
    renderLogin(login);

    await user.type(screen.getByPlaceholderText("Username"), "dr.mueller");
    await user.type(screen.getByPlaceholderText("Passwort"), "wrong");
    await user.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Anmeldung fehlgeschlagen")
    );
  });

  it("shows an error toast when login throws", async () => {
    const login = vi.fn().mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();
    renderLogin(login);

    await user.type(screen.getByPlaceholderText("Username"), "dr.mueller");
    await user.type(screen.getByPlaceholderText("Passwort"), "secret");
    await user.click(screen.getByRole("button", { name: "Anmelden" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Anmeldung fehlgeschlagen")
    );
  });

  it("shows the SSO button when the OIDC status check reports enabled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ enabled: true })));
    renderLogin(vi.fn());

    expect(
      await screen.findByRole("button", { name: /Mit Single Sign-On anmelden/ })
    ).toBeInTheDocument();
  });

  it("hides the SSO button when the OIDC status check reports disabled", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ enabled: false })));
    renderLogin(vi.fn());

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith("/api/v1/auth/oidc/status")
    );
    expect(
      screen.queryByRole("button", { name: /Mit Single Sign-On anmelden/ })
    ).not.toBeInTheDocument();
  });

  it("hides the SSO button when the OIDC status check fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));
    renderLogin(vi.fn());

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(
      screen.queryByRole("button", { name: /Mit Single Sign-On anmelden/ })
    ).not.toBeInTheDocument();
  });

  it("extracts access/refresh tokens from the OIDC callback URL and redirects to the dashboard", async () => {
    renderLogin(vi.fn(), ["/login?access_token=abc123&refresh_token=def456"]);

    await waitFor(() => expect(localStorage.getItem("access_token")).toBe("abc123"));
    expect(localStorage.getItem("refresh_token")).toBe("def456");
    expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
  });

  it("redirects to the dashboard when already authenticated", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      authFetch: vi.fn(),
      acceptDisclaimer: vi.fn(),
    });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Login />
      </MemoryRouter>
    );

    expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
  });
});
