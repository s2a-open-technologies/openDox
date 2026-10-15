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

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Logo } from "@/components/Logo";

describe("Logo", () => {
  it("renders the openDox wordmark", () => {
    render(<Logo />);

    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("Dox")).toBeInTheDocument();
  });

  it("renders an svg root element", () => {
    const { container } = render(<Logo />);

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("viewBox", "-15 10 220 45");
  });

  it("merges a custom className onto the svg via cn()", () => {
    const { container } = render(<Logo className="h-24 w-auto" />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("h-24", "w-auto");
  });

  it("renders without a className prop", () => {
    const { container } = render(<Logo />);

    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
