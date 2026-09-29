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

import { describe, it, expect, afterEach } from "vitest";
import i18n from "@/i18n";
import { apiErrorMessage } from "@/lib/apiError";

describe("apiErrorMessage", () => {
  afterEach(async () => {
    await i18n.changeLanguage("de");
  });

  it("translates a structured error into the current language", async () => {
    const body = { detail: { code: "user_exists", message: "User already exists", params: {} } };

    expect(apiErrorMessage(body, "x")).toBe("Benutzer existiert bereits");
    await i18n.changeLanguage("en");
    expect(apiErrorMessage(body, "x")).toBe("User already exists");
  });

  it("interpolates params", async () => {
    await i18n.changeLanguage("en");
    const body = { detail: { code: "backup_invalid_json", message: "m", params: { error: "boom" } } };

    expect(apiErrorMessage(body, "x")).toBe("Not valid JSON: boom");
  });

  it("falls back to the backend message for an unknown code", () => {
    const body = { detail: { code: "brand_new_code", message: "Backend text", params: {} } };

    expect(apiErrorMessage(body, "x")).toBe("Backend text");
  });

  it("translates probe results that carry a code and an error string", async () => {
    await i18n.changeLanguage("en");

    expect(apiErrorMessage({ ok: false, code: "asr_endpoint_unreachable", error: "Endpoint nicht erreichbar" }, "x")).toBe(
      "Endpoint unreachable"
    );
  });

  it("passes legacy string details and raw errors through", () => {
    expect(apiErrorMessage({ detail: "Too many login attempts" }, "x")).toBe("Too many login attempts");
    expect(apiErrorMessage({ ok: false, error: "provider said no" }, "x")).toBe("provider said no");
  });

  it("uses the fallback for validation-error arrays and non-objects", () => {
    expect(apiErrorMessage({ detail: [{ msg: "bad" }] }, "fallback")).toBe("fallback");
    expect(apiErrorMessage(null, "fallback")).toBe("fallback");
    expect(apiErrorMessage({}, "fallback")).toBe("fallback");
  });
});
