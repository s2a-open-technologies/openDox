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

import "@testing-library/jest-dom";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock;

// Must be set before importing "@/api" so BASE_PATH resolves to "" and the
// window.fetch monkey-patch in api.ts stays inactive during tests.
(window as unknown as Record<string, unknown>).__ROOT_PATH__ = "";

import "@/api";

// Synchronously initialised i18next (German by default) so components using
// useTranslation() work in tests without a provider.
import i18n from "@/i18n";
i18n.changeLanguage("de");

// Reset the mocked system clock between test files so setSystemTime() in one
// file can't leak "frozen new Date()" into another file's expectations.
afterEach(() => {
  vi.useRealTimers();
});
