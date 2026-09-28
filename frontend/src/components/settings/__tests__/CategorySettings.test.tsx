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
import CategorySettings from "@/components/settings/CategorySettings";
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

function renderWithAuth(
  authFetch: ReturnType<typeof vi.fn>,
  role: "admin" | "moderator" | "demo_viewer" | "user" = "admin",
  id = 1
) {
  mockedUseAuth.mockReturnValue({
    user: { id, name: "tester", is_active: true, authenticated: true, role },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<CategorySettings />);
}

async function fillRequiredFields(
  user: ReturnType<typeof userEvent.setup>,
  { name, description, systemPrompt }: { name: string; description: string; systemPrompt: string }
) {
  await user.type(screen.getByPlaceholderText("Kategorie Name"), name);
  await user.type(screen.getByPlaceholderText("Beschreibung"), description);
  await user.type(
    screen.getByPlaceholderText("Anweisungen für die Zusammenfassung, z.B. Format, Struktur, Fokus..."),
    systemPrompt
  );
}

describe("CategorySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the category list with global/own badges and LLM override info", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          id: 1,
          name: "Kardiologie",
          description: "Herzerkrankungen",
          system_prompt: "Fasse zusammen",
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
          user_id: null,
        },
        {
          id: 2,
          name: "Meine Kategorie",
          description: "Privat",
          system_prompt: "Fasse zusammen",
          whisper_prompt: null,
          llm_override_enabled: true,
          llm_model: "gpt-4o",
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
    renderWithAuth(authFetch);

    expect(await screen.findByText("Kardiologie")).toBeInTheDocument();
    expect(screen.getByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Eigene Kategorie")).toBeInTheDocument();
    expect(screen.getByText("LLM: gpt-4o")).toBeInTheDocument();
  });

  it("shows the empty state when there are no categories", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse([]));
    renderWithAuth(authFetch);

    expect(await screen.findByText("Keine Kategorien vorhanden")).toBeInTheDocument();
  });

  it("creates a new category and resets the form", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ id: 5, name: "Neurologie" }))
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 5,
            name: "Neurologie",
            description: "Nervensystem",
            system_prompt: "Prompt",
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
            user_id: null,
          },
        ])
      );
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Keine Kategorien vorhanden");
    await fillRequiredFields(user, {
      name: "Neurologie",
      description: "Nervensystem",
      systemPrompt: "Prompt",
    });
    await user.click(screen.getByRole("button", { name: "Erstellen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/categories/");
    expect(options.method).toBe("POST");
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({
      name: "Neurologie",
      description: "Nervensystem",
      system_prompt: "Prompt",
      llm_override_enabled: false,
      llm_model: null,
    });

    expect(toast.success).toHaveBeenCalledWith("Kategorie erstellt");
    await waitFor(() =>
      expect((screen.getByPlaceholderText("Kategorie Name") as HTMLInputElement).value).toBe("")
    );
  });

  it("sends the glossary field independently of the whisper prompt", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ id: 6, name: "Onkologie" }))
      .mockResolvedValueOnce(jsonResponse([]));
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Keine Kategorien vorhanden");
    await fillRequiredFields(user, {
      name: "Onkologie",
      description: "Krebs",
      systemPrompt: "Prompt",
    });
    await user.type(
      screen.getByPlaceholderText("Kardiologie, Echokardiographie, Sinusbradykardie, Dr. Müller, EKG, Herzinsuffizienz ..."),
      "Stil-Hinweis"
    );
    await user.type(
      screen.getByPlaceholderText("Sertralin, Metformin, Ibuprofen ..."),
      "Sertralin, Ibuprofen"
    );
    await user.click(screen.getByRole("button", { name: "Erstellen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [, options] = authFetch.mock.calls[1];
    const body = JSON.parse(options.body);
    expect(body.whisper_prompt).toBe("Stil-Hinweis");
    expect(body.glossary).toBe("Sertralin, Ibuprofen");
  });

  it("shows the server error detail and keeps the form on create failure", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Name bereits vergeben" }, false));
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Keine Kategorien vorhanden");
    await fillRequiredFields(user, {
      name: "Doppelt",
      description: "Beschreibung",
      systemPrompt: "Prompt",
    });
    await user.click(screen.getByRole("button", { name: "Erstellen" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Name bereits vergeben"));
    expect(screen.getByRole("button", { name: "Erstellen" })).toBeInTheDocument();
    expect((screen.getByPlaceholderText("Kategorie Name") as HTMLInputElement).value).toBe(
      "Doppelt"
    );
  });

  it("pre-fills the edit form and updates the category", async () => {
    const existing = {
      id: 7,
      name: "Alt",
      description: "Alte Beschreibung",
      system_prompt: "Alter Prompt",
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
      user_id: null,
    };
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([existing]))
      .mockResolvedValueOnce(jsonResponse({ ...existing, description: "Neue Beschreibung" }))
      .mockResolvedValueOnce(
        jsonResponse([{ ...existing, description: "Neue Beschreibung" }])
      );
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Alt");
    const editButtons = screen.getAllByRole("button");
    const editButton = editButtons.find((btn) => btn.querySelector("svg.lucide-pencil"));
    await user.click(editButton!);

    expect(screen.getByText("Kategorie bearbeiten")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Alt")).toBeInTheDocument();

    const descriptionInput = screen.getByDisplayValue("Alte Beschreibung");
    await user.clear(descriptionInput);
    await user.type(descriptionInput, "Neue Beschreibung");
    await user.click(screen.getByRole("button", { name: "Aktualisieren" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/categories/7");
    expect(options.method).toBe("PUT");
    expect(toast.success).toHaveBeenCalledWith("Kategorie aktualisiert");
  });

  it("does not delete when the confirmation dialog is declined", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          id: 3,
          name: "Behalten",
          description: "Bleibt",
          system_prompt: "Prompt",
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
          user_id: null,
        },
      ])
    );
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Behalten");
    const deleteButtons = screen.getAllByRole("button");
    const deleteButton = deleteButtons.find((btn) => btn.querySelector("svg.lucide-trash2"));
    await user.click(deleteButton!);

    expect(authFetch).toHaveBeenCalledTimes(1);
  });

  it("deletes the category and refetches when confirmed", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 9,
            name: "Löschen",
            description: "Weg",
            system_prompt: "Prompt",
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
            user_id: null,
          },
        ])
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
      .mockResolvedValueOnce(jsonResponse([]));
    const user = userEvent.setup();
    renderWithAuth(authFetch);

    await screen.findByText("Löschen");
    const deleteButtons = screen.getAllByRole("button");
    const deleteButton = deleteButtons.find((btn) => btn.querySelector("svg.lucide-trash2"));
    await user.click(deleteButton!);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(3));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/categories/9");
    expect(options.method).toBe("DELETE");
    expect(toast.success).toHaveBeenCalledWith("Kategorie gelöscht");
  });

  it("hides manage controls and the LLM-override section for non-privileged users", async () => {
    const authFetch = vi.fn().mockResolvedValue(
      jsonResponse([
        {
          id: 1,
          name: "Global-Kategorie",
          description: "Für alle",
          system_prompt: "Prompt",
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
          user_id: null,
        },
      ])
    );
    renderWithAuth(authFetch, "user", 42);

    await screen.findByText("Global-Kategorie");
    expect(screen.queryByText("Eigenes LLM verwenden")).not.toBeInTheDocument();
    // No edit/delete icon buttons for a plain user on a global category
    const iconButtons = screen
      .queryAllByRole("button")
      .filter((btn) => btn.querySelector("svg.lucide-pencil, svg.lucide-trash2"));
    expect(iconButtons).toHaveLength(0);
  });
});
