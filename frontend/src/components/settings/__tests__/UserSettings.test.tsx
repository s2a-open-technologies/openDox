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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UserSettings from "@/components/settings/UserSettings";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

function renderWithAuthFetch(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<UserSettings />);
}

describe("UserSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the user list with role labels", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        { id: 1, name: "admin1", is_active: true, role: "admin" },
        { id: 2, name: "dr.mueller", is_active: true, role: "user" },
      ])
    );
    renderWithAuthFetch(authFetch);

    expect(await screen.findByText("admin1")).toBeInTheDocument();
    expect(screen.getByText("dr.mueller")).toBeInTheDocument();
    expect(screen.getByText("Administrator")).toBeInTheDocument();
    expect(screen.getByText("Benutzer")).toBeInTheDocument();
  });

  it("shows the empty state when there are no users", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse([]));
    renderWithAuthFetch(authFetch);

    expect(await screen.findByText("Keine Benutzer vorhanden")).toBeInTheDocument();
  });

  it("creates a new user and refetches the list", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ id: 3, name: "new.user" }))
      .mockResolvedValueOnce(
        jsonResponse([{ id: 3, name: "new.user", is_active: true, role: "user" }])
      );
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Keine Benutzer vorhanden");
    await user.click(screen.getByRole("button", { name: /Benutzer anlegen/ }));
    await user.type(screen.getByPlaceholderText("z.B. dr.mueller"), "new.user");
    await user.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/auth/users");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toMatchObject({ name: "new.user", role: "user" });

    expect(toast.success).toHaveBeenCalledWith("Benutzer angelegt");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Anlegen" })).not.toBeInTheDocument()
    );
  });

  it("shows the server error detail and keeps the dialog open on failure", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ detail: "User already exists" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Keine Benutzer vorhanden");
    await user.click(screen.getByRole("button", { name: /Benutzer anlegen/ }));
    await user.type(screen.getByPlaceholderText("z.B. dr.mueller"), "dr.mueller");
    await user.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("User already exists")
    );
    expect(screen.getByRole("button", { name: "Anlegen" })).toBeInTheDocument();
  });

  it("pre-fills the edit dialog with the selected user's data", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([{ id: 1, name: "dr.mueller", is_active: true, role: "user" }])
    );
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("dr.mueller");
    const editButtons = screen.getAllByRole("button");
    const editButton = editButtons.find((btn) =>
      btn.querySelector("svg.lucide-pencil")
    );
    await user.click(editButton!);

    expect(screen.getByText("Benutzer bearbeiten")).toBeInTheDocument();
    expect(screen.getByDisplayValue("dr.mueller")).toBeInTheDocument();
    expect(screen.getByText(/leer = unveraendert/)).toBeInTheDocument();
  });

  it("does not call the API when delete is not confirmed", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([{ id: 1, name: "dr.mueller", is_active: true, role: "user" }])
    );
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("dr.mueller");
    const deleteButtons = screen.getAllByRole("button");
    const deleteButton = deleteButtons.find((btn) =>
      btn.querySelector("svg.lucide-trash2")
    );
    await user.click(deleteButton!);

    expect(authFetch).toHaveBeenCalledTimes(1); // only the initial fetch
  });

  it("deletes the user and refetches when confirmed", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([{ id: 1, name: "dr.mueller", is_active: true, role: "user" }])
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
      .mockResolvedValueOnce(jsonResponse([]));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("dr.mueller");
    const deleteButtons = screen.getAllByRole("button");
    const deleteButton = deleteButtons.find((btn) =>
      btn.querySelector("svg.lucide-trash2")
    );
    await user.click(deleteButton!);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/auth/users/1");
    expect(options.method).toBe("DELETE");
    expect(toast.success).toHaveBeenCalledWith("Benutzer gelöscht");
  });
});
