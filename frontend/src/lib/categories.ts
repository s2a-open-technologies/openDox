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

// Preselected category wherever a recording starts, so the user never lands
// on an empty dropdown: the one an admin set as default for everyone, else
// the shipped "Standard" (is_builtin), else the first one — a recording
// always needs one.
export interface PreselectableCategory {
  id: number;
  is_default?: boolean;
  is_builtin?: boolean;
}

export function defaultCategoryId(categories: PreselectableCategory[]): string | null {
  const chosen =
    categories.find((c) => c.is_default) ??
    categories.find((c) => c.is_builtin) ??
    categories[0];
  return chosen ? chosen.id.toString() : null;
}
