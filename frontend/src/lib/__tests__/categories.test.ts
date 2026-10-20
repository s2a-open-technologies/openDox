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
import { defaultCategoryId } from "@/lib/categories";

describe("defaultCategoryId", () => {
  it("prefers Allgemein", () => {
    expect(
      defaultCategoryId([
        { id: 4, name: "Meine" },
        { id: 1, name: "Allgemein" },
      ])
    ).toBe("1");
  });

  it("falls back to the first category without Allgemein", () => {
    expect(defaultCategoryId([{ id: 4, name: "Meine" }])).toBe("4");
  });

  it("is null without categories", () => {
    expect(defaultCategoryId([])).toBeNull();
  });
});
