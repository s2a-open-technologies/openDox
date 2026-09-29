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

import i18n from "@/i18n";

interface StructuredDetail {
  code?: string;
  message?: string;
  params?: Record<string, unknown>;
}

const translateCode = (code: string, fallback: string | undefined, params?: Record<string, unknown>) =>
  i18n.t(`errors:${code}`, { ...params, defaultValue: fallback ?? code });

/**
 * User-facing message for a failed API call, in the current UI language.
 *
 * Understands the backend's structured errors (`{detail: {code, message, params}}`),
 * probe results (`{code, error}`, e.g. /asr-test/), legacy plain-string
 * details and raw `error` strings. Anything else yields `fallback`.
 */
export const apiErrorMessage = (body: unknown, fallback: string): string => {
  if (!body || typeof body !== "object") return fallback;
  const { detail, code, error } = body as {
    detail?: unknown;
    code?: unknown;
    error?: unknown;
  };

  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as StructuredDetail;
    return d.code ? translateCode(d.code, d.message, d.params) : d.message || fallback;
  }
  if (typeof detail === "string" && detail) return detail;

  if (typeof code === "string" && code) {
    return translateCode(code, typeof error === "string" ? error : undefined);
  }
  if (typeof error === "string" && error) return error;
  return fallback;
};
