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
import ProfileModal from "@/components/ProfileModal";
import { useAuth } from "@/contexts/AuthContext";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", setTheme: vi.fn(), toggleTheme: vi.fn() }),
}));

vi.mock("@/components/settings/CategorySettings", () => ({
  default: () => <div data-testid="category-settings" />,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body } as Response;
}

function renderModal({
  role = "user",
  isOpen = true,
  updateUiLanguage = vi.fn().mockResolvedValue(true),
  authFetch = vi.fn().mockResolvedValue(jsonResponse([])),
}: {
  role?: "admin" | "moderator" | "demo_viewer" | "user";
  isOpen?: boolean;
  updateUiLanguage?: ReturnType<typeof vi.fn>;
  authFetch?: ReturnType<typeof vi.fn>;
} = {}) {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, name: "dr.mueller", is_active: true, authenticated: true, role },
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    authFetch,
    acceptDisclaimer: vi.fn(),
    updateUiLanguage,
  });
  render(<ProfileModal isOpen={isOpen} onClose={vi.fn()} />);
  return { updateUiLanguage, authFetch };
}

describe("ProfileModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom has no pointer-capture / scrollIntoView support, which Radix's
    // Select relies on for its open/select interactions.
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = () => false;
    }
    Element.prototype.setPointerCapture = vi.fn();
    Element.prototype.releasePointerCapture = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders nothing when closed", () => {
    renderModal({ isOpen: false });

    expect(screen.queryByText("Sprache")).not.toBeInTheDocument();
  });

  it("opens on the language tab", () => {
    renderModal();

    expect(screen.getByText("Sprache der Benutzeroberfläche")).toBeInTheDocument();
  });

  it.each(["user", "admin", "moderator"] as const)(
    "offers the categories tab to role %s",
    (role) => {
      renderModal({ role });
      expect(screen.getByRole("button", { name: /Meine Kategorien/ })).toBeInTheDocument();
    }
  );

  it("loads the personal dictionaries when their tab is selected", async () => {
    const user = userEvent.setup();
    const { authFetch } = renderModal();

    await user.click(screen.getByRole("button", { name: /Meine Wörterbücher/ }));

    await waitFor(() =>
      expect(authFetch).toHaveBeenCalledWith("/api/v1/settings/dictionaries/")
    );
  });

  it("saves the chosen language through updateUiLanguage", async () => {
    const user = userEvent.setup();
    const { updateUiLanguage } = renderModal();

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "English" }));

    await waitFor(() => expect(updateUiLanguage).toHaveBeenCalledWith("en"));
  });
});
