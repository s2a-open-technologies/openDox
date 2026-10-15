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
import UserDropdown from "@/components/UserDropdown";
import { useAuth } from "@/contexts/AuthContext";
import i18n from "@/i18n";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/components/AdminModal", () => ({
  default: ({ isOpen }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? <div data-testid="admin-modal">AdminModal</div> : null,
}));

vi.mock("@/components/ProfileModal", () => ({
  default: ({ isOpen }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? <div data-testid="profile-modal">ProfileModal</div> : null,
}));

const mockedUseAuth = vi.mocked(useAuth);

function setup({
  role,
  logout = vi.fn(),
}: {
  role: "admin" | "moderator" | "demo_viewer" | "user";
  logout?: ReturnType<typeof vi.fn>;
}) {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout,
    authFetch: vi.fn(),
    acceptDisclaimer: vi.fn(),
    updateUiLanguage: vi.fn(),
  });
  return render(<UserDropdown />);
}

describe("UserDropdown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the user's name in the trigger button", () => {
    setup({ role: "user" });

    expect(screen.getByText("dr.mueller")).toBeInTheDocument();
  });

  it("shows the German role label for an admin once the menu is opened", async () => {
    const user = userEvent.setup();
    setup({ role: "admin" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Administrator")).toBeInTheDocument();
  });

  it("shows the English role label when the UI language is English", async () => {
    await i18n.changeLanguage("en");
    try {
      const user = userEvent.setup();
      setup({ role: "user" });

      await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

      expect(await screen.findByText("User")).toBeInTheDocument();
      expect(screen.getByText("Profile")).toBeInTheDocument();
      expect(screen.getByText("Log out")).toBeInTheDocument();
    } finally {
      await i18n.changeLanguage("de");
    }
  });

  it("shows 'Profil' and 'Administration' for admins and moderators", async () => {
    const user = userEvent.setup();
    setup({ role: "moderator" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Profil")).toBeInTheDocument();
    expect(screen.getByText("Administration")).toBeInTheDocument();
  });

  it("shows 'Profil' but no 'Administration' for a plain user", async () => {
    const user = userEvent.setup();
    setup({ role: "user" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Profil")).toBeInTheDocument();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  });

  it("opens the AdminModal when 'Administration' is clicked", async () => {
    const user = userEvent.setup();
    setup({ role: "admin" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Administration"));

    await waitFor(() => expect(screen.getByTestId("admin-modal")).toBeInTheDocument());
  });

  it("opens the ProfileModal when 'Profil' is clicked", async () => {
    const user = userEvent.setup();
    setup({ role: "user" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Profil"));

    await waitFor(() => expect(screen.getByTestId("profile-modal")).toBeInTheDocument());
  });

  it("calls logout when 'Abmelden' is clicked", async () => {
    const logout = vi.fn();
    const user = userEvent.setup();
    setup({ role: "user", logout });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Abmelden"));

    expect(logout).toHaveBeenCalledTimes(1);
  });
});
