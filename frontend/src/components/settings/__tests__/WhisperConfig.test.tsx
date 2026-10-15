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
import WhisperConfig from "@/components/settings/WhisperConfig";
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
  live_backend: "api",
  live_api_endpoint: "http://live.example.com:9000",
  live_api_key: "live-key",
  final_backend: "api",
  final_api_endpoint: "http://final.example.com:9000",
  final_api_key: "final-key",
  final_api_model: "large-v3",
  language: "de",
  temperature: 0.0,
  vad_filter: true,
  vad_min_silence_ms: 500,
  condition_on_previous_text: false,
  no_speech_threshold: 0.6,
  compression_ratio_threshold: 2.4,
  log_prob_threshold: -1.0,
  hallucination_silence_threshold: null,
  final_beam_size: 5,
  term_correction_enabled: false,
  term_correction_threshold: 85.0,
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
  return render(<WhisperConfig readOnly={readOnly} />);
}

describe("WhisperConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads settings and displays them across the Live and Final tabs", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");

    await user.click(screen.getByRole("tab", { name: "Live" }));
    expect(screen.getByDisplayValue("http://live.example.com:9000")).toBeInTheDocument();
    expect(screen.getByDisplayValue("live-key")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Final" }));
    expect(screen.getByDisplayValue("http://final.example.com:9000")).toBeInTheDocument();
    expect(screen.getByDisplayValue("final-key")).toBeInTheDocument();
    expect(screen.getByDisplayValue("large-v3")).toBeInTheDocument();
  });

  it.each(["parakeet", "disabled"])(
    "always shows the Qualität tab with the final beam size (live backend: %s)",
    async (liveBackend) => {
      const authFetch = vi
        .fn()
        .mockResolvedValue(jsonResponse({ ...baseSettings, live_backend: liveBackend }));
      const user = userEvent.setup();
      renderWithAuthFetch(authFetch);

      await screen.findByText("Allgemeine Einstellungen");
      await user.click(screen.getByRole("tab", { name: "Qualität" }));

      expect(screen.getByText("Beam-Size")).toBeInTheDocument();
      expect(screen.getByText("VAD min. Stille (ms)")).toBeInTheDocument();
      expect(screen.queryByText("Beam-Size Live")).not.toBeInTheDocument();
    }
  );

  it("shows the parakeet info note and no near-live Whisper fields", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValue(jsonResponse({ ...baseSettings, live_backend: "parakeet" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");
    await user.click(screen.getByRole("tab", { name: "Live" }));

    expect(
      screen.getByText(/Parakeet läuft mit Silero-VAD-gesteuertem Streaming/)
    ).toBeInTheDocument();
    expect(screen.queryByText("Chunk-Länge (Sek.)")).not.toBeInTheDocument();
    expect(screen.queryByText("Überlappung (Sek.)")).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Whisper API" })).not.toBeInTheDocument();
  });

  it("saves settings and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");
    await user.click(screen.getByRole("tab", { name: "Live" }));

    const endpointInput = screen.getByDisplayValue("http://live.example.com:9000");
    await user.clear(endpointInput);
    await user.type(endpointInput, "http://live2.example.com:9000");

    await user.click(screen.getByRole("button", { name: "Einstellungen speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/whisper-settings/");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toMatchObject({
      live_api_endpoint: "http://live2.example.com:9000",
    });

    expect(toast.success).toHaveBeenCalledWith("Einstellungen gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ detail: "bad config" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");
    await user.click(screen.getByRole("button", { name: "Einstellungen speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen"));
  });

  it("tests the live ASR connection and shows the reachable result", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true, model: "large-v3-turbo" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");
    await user.click(screen.getByRole("tab", { name: "Live" }));
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    expect(authFetch.mock.calls[1][0]).toBe("/api/v1/settings/asr-test/?backend=live");
    expect(await screen.findByText("Erreichbar · Modell: large-v3-turbo")).toBeInTheDocument();
  });

  it("tests the final ASR connection and shows an error result", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: false, error: "Nicht erreichbar" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByText("Allgemeine Einstellungen");
    await user.click(screen.getByRole("tab", { name: "Final" }));
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    expect(authFetch.mock.calls[1][0]).toBe("/api/v1/settings/asr-test/?backend=final");
    expect(await screen.findByText("Nicht erreichbar")).toBeInTheDocument();
  });
});
