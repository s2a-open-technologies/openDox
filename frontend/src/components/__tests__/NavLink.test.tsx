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

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { NavLink } from "@/components/NavLink";

describe("NavLink", () => {
  it("renders an anchor with the correct href", () => {
    render(
      <MemoryRouter initialEntries={["/home"]}>
        <NavLink to="/home">Home</NavLink>
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toHaveAttribute("href", "/home");
  });

  it("applies activeClassName when the route matches", () => {
    render(
      <MemoryRouter initialEntries={["/home"]}>
        <NavLink to="/home" className="base" activeClassName="is-active">
          Home
        </NavLink>
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toHaveClass("base", "is-active");
  });

  it("does not apply activeClassName for a non-matching route", () => {
    render(
      <MemoryRouter initialEntries={["/other"]}>
        <NavLink to="/home" className="base" activeClassName="is-active">
          Home
        </NavLink>
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toHaveClass("base");
    expect(link).not.toHaveClass("is-active");
  });

  it("distinguishes the active link among several NavLinks", () => {
    render(
      <MemoryRouter initialEntries={["/records"]}>
        <NavLink to="/home" activeClassName="is-active">
          Home
        </NavLink>
        <NavLink to="/records" activeClassName="is-active">
          Records
        </NavLink>
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: "Home" })).not.toHaveClass("is-active");
    expect(screen.getByRole("link", { name: "Records" })).toHaveClass("is-active");
  });

  it("forwards a ref to the underlying anchor element", () => {
    let anchorEl: HTMLAnchorElement | null = null;

    render(
      <MemoryRouter initialEntries={["/"]}>
        <NavLink
          to="/"
          ref={(el) => {
            anchorEl = el;
          }}
        >
          Root
        </NavLink>
      </MemoryRouter>
    );

    expect(anchorEl).toBeInstanceOf(HTMLAnchorElement);
  });

  it("works inside Routes without crashing on navigation targets", () => {
    render(
      <MemoryRouter initialEntries={["/a"]}>
        <NavLink to="/a">A</NavLink>
        <NavLink to="/b">B</NavLink>
        <Routes>
          <Route path="/a" element={<div>Page A</div>} />
          <Route path="/b" element={<div>Page B</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Page A")).toBeInTheDocument();
  });
});
