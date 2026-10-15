/*
  openDox - Medical transcription platform
  Copyright (C) 2026  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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
import { ClientConfig } from "@/components/settings/ClientConfig";
import { ClientDistribution } from "@/components/settings/ClientDistribution";
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

function mockAuth(authFetch: ReturnType<typeof vi.fn>) {
  mockedUseAuth.mockReturnValue({
    user: null,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
  });
}

const serverConfig = {
  clipboard_exclude_from_history: true,
  clipboard_clear_after_seconds: 45,
  insert_allowlist: ["medistar.exe", "winword.exe"],
  dictation_mic_mode: "toggle",
  live_view: false,
};

describe("ClientConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the client policy and shows the allowlist one per line", async () => {
    mockAuth(vi.fn().mockResolvedValue(jsonResponse(serverConfig)));
    render(<ClientConfig />);

    await waitFor(() =>
      expect(
        (screen.getByLabelText("Record-Taste am Diktiermikrofon") as HTMLSelectElement).value
      ).toBe("toggle")
    );
    expect(
      (screen.getByLabelText("Erlaubte Zielprogramme (ein Programm pro Zeile)") as HTMLTextAreaElement).value
    ).toBe("medistar.exe\nwinword.exe");
    expect(
      (screen.getByLabelText("Zwischenablage leeren nach (Sekunden)") as HTMLInputElement).value
    ).toBe("45");
  });

  it("sends the allowlist as a list when saving", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(serverConfig))
      .mockResolvedValueOnce(jsonResponse({ ...serverConfig, insert_allowlist: ["notepad.exe"] }));
    mockAuth(authFetch);
    const user = userEvent.setup();
    render(<ClientConfig />);

    const allowlist = screen.getByLabelText("Erlaubte Zielprogramme (ein Programm pro Zeile)");
    await waitFor(() => expect((allowlist as HTMLTextAreaElement).value).toContain("medistar"));
    await user.clear(allowlist);
    await user.type(allowlist, "notepad.exe");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/client-config/");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body).insert_allowlist).toEqual(["notepad.exe"]);
    expect(toast.success).toHaveBeenCalledWith("Client-Einstellungen gespeichert");
  });

  it("disables saving in read-only mode", async () => {
    mockAuth(vi.fn().mockResolvedValue(jsonResponse(serverConfig)));
    render(<ClientConfig readOnly />);

    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});

describe("ClientDistribution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("links the installers and shows the server address", async () => {
    mockAuth(
      vi.fn().mockResolvedValue(
        jsonResponse({
          server_url: "https://dox.klinik.de",
          download_base_url: "https://example.org/latest/download",
          files: { windows_msi: "opendox-client-installer.msi" },
        })
      )
    );
    render(<ClientDistribution />);

    const link = await screen.findByRole("link", { name: /MSI/ });
    expect(link).toHaveAttribute(
      "href",
      "https://example.org/latest/download/opendox-client-installer.msi"
    );
    expect(screen.getByText("https://dox.klinik.de")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /macOS/ })).not.toBeInTheDocument();
  });
});
