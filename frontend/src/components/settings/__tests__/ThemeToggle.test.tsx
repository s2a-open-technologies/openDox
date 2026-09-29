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
import { ThemeToggle } from "@/components/settings/ThemeToggle";
import { useTheme } from "@/contexts/ThemeContext";

vi.mock("@/contexts/ThemeContext", () => ({
  useTheme: vi.fn(),
}));

const mockedUseTheme = vi.mocked(useTheme);

function renderWithTheme(theme: "light" | "dark" | "system", setTheme = vi.fn()) {
  mockedUseTheme.mockReturnValue({ theme, setTheme, toggleTheme: vi.fn() });
  return render(<ThemeToggle />);
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Hell, Dunkel and System buttons", () => {
    renderWithTheme("light");

    expect(screen.getByRole("button", { name: /Hell/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dunkel/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /System/ })).toBeInTheDocument();
  });

  it("highlights the currently active theme button", () => {
    renderWithTheme("dark");

    expect(screen.getByRole("button", { name: /Dunkel/ }).className).toContain("bg-primary");
    expect(screen.getByRole("button", { name: /Hell/ }).className).toContain("border-input");
    expect(screen.getByRole("button", { name: /System/ }).className).toContain("border-input");
  });

  it("calls setTheme('dark') when the Dark button is clicked", async () => {
    const setTheme = vi.fn();
    const user = userEvent.setup();
    renderWithTheme("light", setTheme);

    await user.click(screen.getByRole("button", { name: /Dunkel/ }));

    expect(setTheme).toHaveBeenCalledWith("dark");
  });

  it("calls setTheme('system') when the System button is clicked", async () => {
    const setTheme = vi.fn();
    const user = userEvent.setup();
    renderWithTheme("light", setTheme);

    await user.click(screen.getByRole("button", { name: /System/ }));

    expect(setTheme).toHaveBeenCalledWith("system");
  });

  it("calls setTheme('light') when the Light button is clicked", async () => {
    const setTheme = vi.fn();
    const user = userEvent.setup();
    renderWithTheme("dark", setTheme);

    await user.click(screen.getByRole("button", { name: /Hell/ }));

    expect(setTheme).toHaveBeenCalledWith("light");
  });
});
