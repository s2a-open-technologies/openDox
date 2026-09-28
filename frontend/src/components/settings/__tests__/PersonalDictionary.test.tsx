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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PersonalDictionary from "@/components/settings/PersonalDictionary";
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

function renderWithAuth(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role: "user" },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<PersonalDictionary />);
}

describe("PersonalDictionary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and pre-fills the current personal glossary", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse({ personal_glossary: "Sertralin, Ibuprofen" })
    );
    renderWithAuth(authFetch);

    expect(await screen.findByDisplayValue("Sertralin, Ibuprofen")).toBeInTheDocument();
    expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/my-dictionary/");
  });

  it("shows an empty textarea when no glossary is set yet", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({ personal_glossary: null }));
    renderWithAuth(authFetch);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(1));
    expect(screen.getByPlaceholderText("Sertralin, Metformin, Ibuprofen ...")).toHaveValue("");
  });

  it("saves the edited glossary via PUT", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ personal_glossary: null }))
      .mockResolvedValueOnce(jsonResponse({ personal_glossary: "Metformin" }));
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    const textarea = await screen.findByPlaceholderText("Sertralin, Metformin, Ibuprofen ...");
    await user.type(textarea, "Metformin");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/my-dictionary/");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toEqual({ personal_glossary: "Metformin" });
    expect(toast.success).toHaveBeenCalledWith("Wörterbuch gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ personal_glossary: null }))
      .mockResolvedValueOnce(jsonResponse({}, false));
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByPlaceholderText("Sertralin, Metformin, Ibuprofen ...");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen"));
  });
});
