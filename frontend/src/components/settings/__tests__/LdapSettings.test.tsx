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
import LdapSettings from "@/components/settings/LdapSettings";
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
// jsdom doesn't implement. LdapSettings wraps its switches in a <form>, which
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
  server_host: "ldap.initial.example.com",
  server_port: 389,
  use_ssl: false,
  base_dn: "dc=example,dc=com",
  user_dn: "uid",
  search_filter: "",
  bind_user_dn: "cn=admin,dc=example,dc=com",
  bind_user_password: "",
  cert_filename: "",
  allowed_groups: "opendox-user",
  admin_groups: "opendox-admin",
  moderator_groups: "opendox-moderatoren",
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
  return render(<LdapSettings readOnly={readOnly} />);
}

describe("LdapSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads and displays the existing LDAP settings", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    renderWithAuthFetch(authFetch);

    expect(await screen.findByDisplayValue("ldap.initial.example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("389")).toBeInTheDocument();
    expect(screen.getByDisplayValue("dc=example,dc=com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("opendox-admin")).toBeInTheDocument();
    // SSL is off, so the cert upload section should not be rendered
    expect(screen.queryByText("Zertifikat hochladen")).not.toBeInTheDocument();
  });

  it("shows the cert upload section and switches the port when SSL is enabled", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("ldap.initial.example.com");
    expect(screen.getByDisplayValue("389")).toBeInTheDocument();

    await user.click(screen.getByRole("switch", { name: "SSL (LDAPS) verwenden" }));

    expect(screen.getByDisplayValue("636")).toBeInTheDocument();
    expect(screen.getByText("Zertifikat hochladen")).toBeInTheDocument();

    await user.click(screen.getByRole("switch", { name: "SSL (LDAPS) verwenden" }));
    expect(screen.getByDisplayValue("389")).toBeInTheDocument();
    expect(screen.queryByText("Zertifikat hochladen")).not.toBeInTheDocument();
  });

  it("uploads a certificate and stores the returned filename", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ ...baseSettings, use_ssl: true }))
      .mockResolvedValueOnce(jsonResponse({ filename: "ca-cert.pem" }));
    const user = userEvent.setup();
    const { container } = renderWithAuthFetch(authFetch);

    await screen.findByText("Zertifikat hochladen");

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["dummy-cert"], "ca-cert.pem", { type: "application/x-pem-file" });
    await user.upload(fileInput, file);

    const uploadButton = screen.getByRole("button", { name: /Upload/ });
    expect(uploadButton).toBeEnabled();
    await user.click(uploadButton);

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/ldap-settings/upload-cert/");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);

    expect(await screen.findByText("ca-cert.pem")).toBeInTheDocument();
  });

  it("saves settings and shows a success toast", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    const hostInput = await screen.findByDisplayValue("ldap.initial.example.com");
    await user.clear(hostInput);
    await user.type(hostInput, "ldap.updated.example.com");

    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/ldap-settings/");
    expect(options.method).toBe("PUT");
    expect(options.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(options.body)).toMatchObject({
      server_host: "ldap.updated.example.com",
    });

    expect(toast.success).toHaveBeenCalledWith("LDAP-Einstellungen gespeichert");
  });

  it("shows an error toast when saving fails", async () => {
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid" }, false));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("ldap.initial.example.com");
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

    await screen.findByDisplayValue("ldap.initial.example.com");
    await user.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Verbindungsfehler"));
  });

  it("tests the connection and alerts with the server message", async () => {
    vi.stubGlobal("alert", vi.fn());
    const authFetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(baseSettings))
      .mockResolvedValueOnce(jsonResponse({ message: "Verbindung erfolgreich" }));
    const user = userEvent.setup();
    renderWithAuthFetch(authFetch);

    await screen.findByDisplayValue("ldap.initial.example.com");
    await user.click(screen.getByRole("button", { name: "Verbindung testen" }));

    await waitFor(() => expect(authFetch).toHaveBeenCalledTimes(2));
    const [url, options] = authFetch.mock.calls[1];
    expect(url).toBe("/api/v1/settings/ldap-settings/test");
    expect(options.method).toBe("POST");
    expect(window.alert).toHaveBeenCalledWith("Verbindung erfolgreich");
  });

  it("disables inputs and buttons in read-only mode", async () => {
    const authFetch = vi.fn().mockResolvedValue(jsonResponse(baseSettings));
    renderWithAuthFetch(authFetch, true);

    const hostInput = await screen.findByDisplayValue("ldap.initial.example.com");
    expect(hostInput).toBeDisabled();
    expect(screen.getByRole("button", { name: "Speichern" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Verbindung testen" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "SSL (LDAPS) verwenden" })).toBeDisabled();
  });
});
