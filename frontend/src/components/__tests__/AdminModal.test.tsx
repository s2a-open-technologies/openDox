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
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminModal from "@/components/AdminModal";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/components/Logo", () => ({
  Logo: () => <div data-testid="logo" />,
}));

function stub(testId: string) {
  return ({ readOnly }: { readOnly?: boolean } = {}) => (
    <div data-testid={testId}>{readOnly ? "readOnly" : "editable"}</div>
  );
}

vi.mock("@/components/settings/WhisperConfig", () => ({ default: stub("whisper-config") }));
vi.mock("@/components/settings/LlmConfig", () => ({ default: stub("llm-config") }));
vi.mock("@/components/settings/OidcSettings", () => ({ default: stub("oidc-settings") }));
vi.mock("@/components/settings/LdapSettings", () => ({ default: stub("ldap-settings") }));
vi.mock("@/components/settings/UserSettings", () => ({ default: stub("user-settings") }));
vi.mock("@/components/settings/SystemSettings", () => ({ default: stub("system-settings") }));
vi.mock("@/components/settings/CategorySettings", () => ({ default: stub("category-settings") }));
vi.mock("@/components/settings/BackupSettings", () => ({ default: stub("backup-settings") }));
vi.mock("@/components/settings/AudioConfig", () => ({ AudioConfig: stub("audio-config") }));
vi.mock("@/components/settings/FailedTranscriptions", () => ({
  FailedTranscriptions: stub("failed-transcriptions"),
}));

const mockedUseAuth = vi.mocked(useAuth);

function renderAdminModal(role: "admin" | "moderator" | "demo_viewer" | "user") {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch: vi.fn(),
    acceptDisclaimer: vi.fn(),
  });
  return render(<AdminModal isOpen={true} onClose={vi.fn()} />);
}

describe("AdminModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 1, name: "admin1", is_active: true, authenticated: true, role: "admin" },
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      authFetch: vi.fn(),
      acceptDisclaimer: vi.fn(),
    });
    render(<AdminModal isOpen={false} onClose={vi.fn()} />);

    expect(screen.queryByTestId("logo")).not.toBeInTheDocument();
  });

  it("shows all admin nav items and defaults to the Dienste tab for an admin", () => {
    renderAdminModal("admin");

    for (const label of ["Dienste", "Audio", "Benutzer", "Authentifizierung", "Backup", "Kategorien", "System"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(screen.getByTestId("whisper-config")).toBeInTheDocument();
    expect(screen.getByTestId("whisper-config")).toHaveTextContent("editable");
  });

  it("shows all admin nav items for a demo_viewer, in a read-only banner", () => {
    renderAdminModal("demo_viewer");

    expect(screen.getByRole("button", { name: /Dienste/ })).toBeInTheDocument();
    expect(screen.getByText(/Nur-Lese-Modus \(Demo\)/)).toBeInTheDocument();
    expect(screen.getByTestId("whisper-config")).toHaveTextContent("readOnly");
  });

  it("hides admin-only nav items for a moderator and defaults to Kategorien", () => {
    renderAdminModal("moderator");

    expect(screen.queryByRole("button", { name: /Dienste/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Benutzer/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kategorien/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /System/ })).toBeInTheDocument();
    expect(screen.getByTestId("category-settings")).toBeInTheDocument();
    expect(screen.queryByText(/Nur-Lese-Modus \(Demo\)/)).not.toBeInTheDocument();
  });

  it("hides admin-only nav items for a plain user and defaults to Kategorien", () => {
    renderAdminModal("user");

    expect(screen.queryByRole("button", { name: /Dienste/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("category-settings")).toBeInTheDocument();
  });

  it("switches to the Audio tab and renders AudioConfig + FailedTranscriptions", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    await user.click(screen.getByRole("button", { name: /Audio/ }));

    expect(screen.getByTestId("audio-config")).toBeInTheDocument();
    expect(screen.getByTestId("failed-transcriptions")).toBeInTheDocument();
    expect(screen.queryByTestId("whisper-config")).not.toBeInTheDocument();
  });

  it("switches to the Benutzer tab and renders UserSettings", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    await user.click(screen.getByRole("button", { name: /Benutzer/ }));

    expect(screen.getByTestId("user-settings")).toBeInTheDocument();
  });

  it("switches to the Backup tab and renders BackupSettings", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    await user.click(screen.getByRole("button", { name: /Backup/ }));

    expect(screen.getByTestId("backup-settings")).toBeInTheDocument();
  });

  it("switches to the System tab and renders SystemSettings", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    await user.click(screen.getByRole("button", { name: /System/ }));

    expect(screen.getByTestId("system-settings")).toBeInTheDocument();
  });

  it("shows LDAP by default and switches to OIDC within the Authentifizierung tab", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    await user.click(screen.getByRole("button", { name: /Authentifizierung/ }));
    expect(screen.getByTestId("ldap-settings")).toBeInTheDocument();
    expect(screen.queryByTestId("oidc-settings")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "OIDC / SSO" }));
    expect(screen.getByTestId("oidc-settings")).toBeInTheDocument();
  });

  it("switches between the Whisper/ASR and LLM sub-tabs of Dienste", async () => {
    const user = userEvent.setup();
    renderAdminModal("admin");

    expect(screen.getByTestId("whisper-config")).toBeInTheDocument();
    expect(screen.queryByTestId("llm-config")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /LLM/ }));
    expect(screen.getByTestId("llm-config")).toBeInTheDocument();
  });
});
