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

// "Allgemein" is the preselected category wherever a recording starts, so the
// user never lands on an empty dropdown; falls back to the first category if
// it was renamed/deleted — a recording always needs one.
export function defaultCategoryId(categories: { id: number; name: string }[]): string | null {
  const allgemein = categories.find((c) => c.name === "Allgemein");
  if (allgemein) return allgemein.id.toString();
  return categories.length > 0 ? categories[0].id.toString() : null;
}
