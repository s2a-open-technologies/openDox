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
import MyCategoriesModal from "@/components/MyCategoriesModal";
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
  return render(<MyCategoriesModal isOpen={isOpen} onClose={vi.fn()} />);
}

describe("MyCategoriesModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse([]));
    renderModal(authFetch, false);

    expect(screen.queryByText("Meine Kategorien")).not.toBeInTheDocument();
  });

  it("shows the dialog title and description when open", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse([]));
    renderModal(authFetch, true);

    expect(screen.getByText("Meine Kategorien")).toBeInTheDocument();
    expect(
      screen.getByText(/Eigene Kategorien für Ihre Aufnahmen anlegen und verwalten/)
    ).toBeInTheDocument();
    await waitFor(() => expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/categories/"));
  });

  it("renders the fetched category list from CategorySettings", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          id: 1,
          name: "Kardiologie",
          description: "Herz-Kreislauf",
          system_prompt: "prompt",
          whisper_prompt: null,
          llm_override_enabled: false,
          llm_model: null,
          llm_api_endpoint: null,
          llm_api_key: null,
          llm_temperature: null,
          llm_max_tokens: null,
          llm_top_p: null,
          llm_frequency_penalty: null,
          llm_enable_thinking: null,
          user_id: 1,
        },
      ])
    );
    renderModal(authFetch, true);

    expect(await screen.findByText("Kardiologie")).toBeInTheDocument();
    expect(screen.getByText("Herz-Kreislauf")).toBeInTheDocument();
    expect(screen.getByText("Eigene Kategorie")).toBeInTheDocument();
  });

  it("creates a new category via authFetch and refetches the list", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ id: 2 }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 2,
            name: "Neuro",
            description: "Neurologie",
            system_prompt: "sys",
            whisper_prompt: null,
            llm_override_enabled: false,
            llm_model: null,
            llm_api_endpoint: null,
            llm_api_key: null,
            llm_temperature: null,
            llm_max_tokens: null,
            llm_top_p: null,
            llm_frequency_penalty: null,
            llm_enable_thinking: null,
            user_id: 1,
          },
        ])
      );
    const user = userEvent.setup();
    renderModal(authFetch, true);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(1));

    await user.type(screen.getByPlaceholderText("Kategorie Name"), "Neuro");
    await user.type(screen.getByPlaceholderText("Beschreibung"), "Neurologie");
    await user.type(
      screen.getByPlaceholderText(/Anweisungen für die Zusammenfassung/),
      "sys"
    );
    await user.click(screen.getByRole("button", { name: "Erstellen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/categories/");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toMatchObject({ name: "Neuro", description: "Neurologie" });
    expect(toast.success).toHaveBeenCalledWith("Kategorie erstellt");
    expect(await screen.findByText("Neuro")).toBeInTheDocument();
  });
});
