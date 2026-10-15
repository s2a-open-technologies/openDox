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

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LlmConfig from "@/components/settings/LlmConfig";
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

const baseSettings = {
  llm_api_endpoint: "http://ollama.example.com:11434/v1",
  llm_api_key: "sk-llm-key",
  llm_model: "medgemma-4b-it:Q4_K_M",
  llm_temperature: 0.3,
  llm_max_tokens: 4096,
  llm_top_p: 0.85,
  llm_frequency_penalty: 0.1,
  llm_enable_thinking: false,
  correction_model: "qwen2.5:0.5b",
  sanitizer_enabled: false,
  sanitizer_endpoint: "",
  sanitizer_api_key: "",
};

function renderWithAuthFetch(authFetch: ReturnType<typeof vi.fn>, readOnly = false) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
  return render(<LlmConfig readOnly={readOnly} />);
}

describe("LlmConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and displays the existing LLM settings", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    renderWithAuthFetch(authFetch);

    expect(
      await screen.findByDisplayValue("http://ollama.example.com:11434/v1")
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("sk-llm-key")).toBeInTheDocument();
    expect(screen.getByDisplayValue("medgemma-4b-it:Q4_K_M")).toBeInTheDocument();
    expect(screen.getByDisplayValue("qwen2.5:0.5b")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.3")).toBeInTheDocument();
    expect(screen.getByDisplayValue("4096")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.85")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Thinking aktivieren" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "Sanitizer aktivieren" })).not.toBeChecked();
    // Sanitizer sub-fields are hidden while disabled
    expect(screen.queryByText("Sanitizer Endpoint (vollständige URL)")).not.toBeInTheDocument();
  });

  it("shows the sanitizer endpoint fields once the sanitizer is enabled", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    expect(screen.queryByText("Sanitizer Endpoint (vollständige URL)")).not.toBeInTheDocument();

    await user.click(screen.getByRole("switch", { name: "Sanitizer aktivieren" }));

    expect(screen.getByText("Sanitizer Endpoint (vollständige URL)")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("http://entityguard:9500/api/v1/sanitize")
    ).toBeInTheDocument();
  });

  it("saves settings and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    const modelInput = await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    await user.clear(modelInput);
    await user.type(modelInput, "llama3:8b");

    await user.click(screen.getByRole("button", { name: "Einstellungen speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/llm-settings/");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toMatchObject({ llm_model: "llama3:8b" });

    expect(toast.success).toHaveBeenCalledWith("Einstellungen gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ detail: "bad config" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    await user.click(screen.getByRole("button", { name: "Einstellungen speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen"));
  });

  it("shows the reply when the connection test succeeds", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true, reply: "Hallo!" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    expect(authFetch.mock.calls[1][0]).toBe("/api/v1/settings/llm-test/");
    expect(await screen.findByText(/Verbunden · Antwort: „Hallo!"/)).toBeInTheDocument();
  });

  it("shows the server error message when the connection test fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: false, error: "Modell nicht gefunden" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    expect(await screen.findByText("Modell nicht gefunden")).toBeInTheDocument();
  });

  it("shows a generic failure message when the connection test request throws", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockRejectedValueOnce(new Error("network down"));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("medgemma-4b-it:Q4_K_M");
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    expect(await screen.findByText("Anfrage fehlgeschlagen")).toBeInTheDocument();
  });
});
