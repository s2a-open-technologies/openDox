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
import DisclaimerGate from "@/components/DisclaimerGate";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const mockedUseAuth = vi.mocked(useAuth);

describe("DisclaimerGate", () => {
  const acceptDisclaimer = vi.fn();
  const logout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: true,
      login: vi.fn(),
      logout,
      authFetch: vi.fn(),
      acceptDisclaimer,
    });
  });

  it("shows the disclaimer alert and a disabled confirm button initially", () => {
    render(<DisclaimerGate />);

    expect(screen.getByText("Kein Medizinprodukt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bestätigen" })).toBeDisabled();
  });

  it("enables the confirm button once the checkbox is checked", async () => {
    const user = userEvent.setup();
    render(<DisclaimerGate />);

    await user.click(screen.getByRole("checkbox"));

    expect(screen.getByRole("button", { name: "Bestätigen" })).toBeEnabled();
  });

  it("calls acceptDisclaimer once and shows no error toast on success", async () => {
    acceptDisclaimer.mockResolvedValue(true);
    const user = userEvent.setup();
    render(<DisclaimerGate />);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));

    expect(acceptDisclaimer).toHaveBeenCalledTimes(1);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("shows an error toast when acceptDisclaimer resolves false", async () => {
    acceptDisclaimer.mockResolvedValue(false);
    const user = userEvent.setup();
    render(<DisclaimerGate />);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Bestätigung fehlgeschlagen – bitte erneut versuchen"
    );
  });

  it("calls logout when clicking Abmelden", async () => {
    const user = userEvent.setup();
    render(<DisclaimerGate />);

    await user.click(screen.getByRole("button", { name: "Abmelden" }));

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("shows a submitting state and disables the button while pending", async () => {
    let resolveAccept: (value: boolean) => void = () => {};
    acceptDisclaimer.mockReturnValue(
      new Promise<boolean>((resolve) => {
        resolveAccept = resolve;
      })
    );
    const user = userEvent.setup();
    render(<DisclaimerGate />);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));

    expect(screen.getByRole("button", { name: "Bestätige..." })).toBeDisabled();

    resolveAccept(true);
  });
});
