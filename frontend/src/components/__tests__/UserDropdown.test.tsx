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
import UserDropdown from "@/components/UserDropdown";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: vi.fn(),
}));

vi.mock("@/components/AdminModal", () => ({
  default: ({ isOpen }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? <div data-testid="admin-modal">AdminModal</div> : null,
}));

vi.mock("@/components/MyCategoriesModal", () => ({
  default: ({ isOpen }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? <div data-testid="my-categories-modal">MyCategoriesModal</div> : null,
}));

vi.mock("@/components/MyDictionaryModal", () => ({
  default: ({ isOpen }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? <div data-testid="my-dictionary-modal">MyDictionaryModal</div> : null,
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedUseTheme = vi.mocked(useTheme);

function setup({
  role,
  logout = vi.fn(),
  toggleTheme = vi.fn(),
  theme = "light",
}: {
  role: "admin" | "moderator" | "demo_viewer" | "user";
  logout?: ReturnType<typeof vi.fn>;
  toggleTheme?: ReturnType<typeof vi.fn>;
  theme?: "light" | "dark";
}) {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout,
    authFetch: vi.fn(),
    acceptDisclaimer: vi.fn(),
  });
  mockedUseTheme.mockReturnValue({ theme, setTheme: vi.fn(), toggleTheme });
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

  it("shows 'Administration' for admins and moderators instead of 'Meine Kategorien'", async () => {
    const user = userEvent.setup();
    setup({ role: "moderator" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Administration")).toBeInTheDocument();
    expect(screen.queryByText("Meine Kategorien")).not.toBeInTheDocument();
  });

  it("shows 'Meine Kategorien' instead of 'Administration' for a plain user", async () => {
    const user = userEvent.setup();
    setup({ role: "user" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Meine Kategorien")).toBeInTheDocument();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
  });

  it("opens the AdminModal when 'Administration' is clicked", async () => {
    const user = userEvent.setup();
    setup({ role: "admin" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Administration"));

    await waitFor(() => expect(screen.getByTestId("admin-modal")).toBeInTheDocument());
  });

  it("opens MyCategoriesModal when 'Meine Kategorien' is clicked", async () => {
    const user = userEvent.setup();
    setup({ role: "user" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Meine Kategorien"));

    await waitFor(() =>
      expect(screen.getByTestId("my-categories-modal")).toBeInTheDocument()
    );
  });

  it("shows 'Mein Wörterbuch' for every role", async () => {
    const user = userEvent.setup();
    setup({ role: "admin" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Mein Wörterbuch")).toBeInTheDocument();
  });

  it("opens MyDictionaryModal when 'Mein Wörterbuch' is clicked", async () => {
    const user = userEvent.setup();
    setup({ role: "user" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Mein Wörterbuch"));

    await waitFor(() =>
      expect(screen.getByTestId("my-dictionary-modal")).toBeInTheDocument()
    );
  });

  it("calls logout when 'Abmelden' is clicked", async () => {
    const logout = vi.fn();
    const user = userEvent.setup();
    setup({ role: "user", logout });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    await user.click(await screen.findByText("Abmelden"));

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("calls toggleTheme and labels the item for the current theme", async () => {
    const toggleTheme = vi.fn();
    const user = userEvent.setup();
    setup({ role: "user", toggleTheme, theme: "light" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));
    expect(await screen.findByText("Dunkles Design")).toBeInTheDocument();
    await user.click(screen.getByText("Dunkles Design"));

    expect(toggleTheme).toHaveBeenCalledTimes(1);
  });

  it("labels the theme item for 'Helles Design' when theme is dark", async () => {
    const user = userEvent.setup();
    setup({ role: "user", theme: "dark" });

    await user.click(screen.getByRole("button", { name: /dr.mueller/ }));

    expect(await screen.findByText("Helles Design")).toBeInTheDocument();
  });
});
