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
import OidcSettings from "@/components/settings/OidcSettings";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

// Radix Switch's hidden bubble-input sizing hook needs ResizeObserver, which
// jsdom doesn't implement. OidcSettings wraps its switch in a <form>, which
// is what triggers that hook, so it's polyfilled here (not in shared setup).
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

const baseSettings = {
  enabled: true,
  provider_url: "https://keycloak.example.com/realms/opendox",
  client_id: "opendox-client",
  client_secret: "top-secret",
  scopes: "openid email profile",
  group_claim: "groups",
  admin_groups: "opendox-admin",
  moderator_groups: "opendox-moderator",
  username_claim: "preferred_username",
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
  return render(<OidcSettings readOnly={readOnly} />);
}

describe("OidcSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads and displays the existing OIDC settings", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    renderWithAuthFetch(authFetch);

    expect(
      await screen.findByDisplayValue("https://keycloak.example.com/realms/opendox")
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("opendox-client")).toBeInTheDocument();
    expect(screen.getByDisplayValue("top-secret")).toBeInTheDocument();
    expect(screen.getByDisplayValue("opendox-admin")).toBeInTheDocument();
    expect(screen.getByDisplayValue("opendox-moderator")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "OIDC aktivieren" })).toBeChecked();
  });

  it("keeps default values when the API response has no provider_url", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse({}));
    renderWithAuthFetch(authFetch);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(1));
    // The guard `data.provider_url !== undefined` fails, so defaults stay in place.
    expect(screen.getByDisplayValue("openid email profile")).toBeInTheDocument();
    expect(screen.getByDisplayValue("groups")).toBeInTheDocument();
    expect(screen.getByDisplayValue("preferred_username")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "OIDC aktivieren" })).not.toBeChecked();
  });

  it("toggles OIDC on, saves, and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ ...baseSettings, enabled: false }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("opendox-client");
    const enableSwitch = screen.getByRole("switch", { name: "OIDC aktivieren" });
    expect(enableSwitch).not.toBeChecked();
    await user.click(enableSwitch);

    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/oidc-settings/");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toMatchObject({ enabled: true });

    expect(toast.success).toHaveBeenCalledWith("OIDC-Einstellungen gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ detail: "bad config" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("opendox-client");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Speichern fehlgeschlagen"));
  });

  it("shows a connection-error toast when the save request throws", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockRejectedValueOnce(new Error("network down"));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("opendox-client");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Verbindungsfehler"));
  });

  it("disables inputs and the save button in read-only mode", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    renderWithAuthFetch(authFetch, true);

    await screen.findByDisplayValue("opendox-client");
    expect(screen.getByDisplayValue("opendox-client")).toBeDisabled();
    expect(screen.getByRole("switch", { name: "OIDC aktivieren" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
  });
});
