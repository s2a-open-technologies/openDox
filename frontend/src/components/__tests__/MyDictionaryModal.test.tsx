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
import MyDictionaryModal from "@/components/MyDictionaryModal";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

function renderModal(authFetch: ReturnType<typeof vi.fn>, isOpen = true) {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role: "user" },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<MyDictionaryModal isOpen={isOpen} onClose={vi.fn()} />);
}

describe("MyDictionaryModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({ personal_glossary: null }));
    renderModal(authFetch, false);

    expect(screen.queryByText("Mein Wörterbuch")).not.toBeInTheDocument();
  });

  it("shows the dialog title and description, and fetches the glossary when open", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({ personal_glossary: null }));
    renderModal(authFetch, true);

    expect(screen.getByText("Mein Wörterbuch")).toBeInTheDocument();
    expect(
      screen.getByText(/unabhängig von der gewählten Kategorie/)
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/my-dictionary/")
    );
  });
});
