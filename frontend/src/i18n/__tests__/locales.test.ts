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
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const LOCALES_DIR = join(__dirname, "..", "locales");
const REFERENCE = "de";

type Json = { [key: string]: Json | string };

function flatten(obj: Json, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out[path] = value;
    else Object.assign(out, flatten(value, path));
  }
  return out;
}

const load = (lang: string, file: string) =>
  flatten(JSON.parse(readFileSync(join(LOCALES_DIR, lang, file), "utf-8")));

const placeholders = (text: string) => [...text.matchAll(/{{\s*(\w+)\s*}}/g)].map((m) => m[1]).sort();

const languages = readdirSync(LOCALES_DIR).filter((d) => d !== REFERENCE);
const namespaces = readdirSync(join(LOCALES_DIR, REFERENCE));

describe.each(languages)("locale '%s' vs. German reference", (lang) => {
  it("has exactly the same namespace files", () => {
    expect(readdirSync(join(LOCALES_DIR, lang)).sort()).toEqual([...namespaces].sort());
  });

  it.each(namespaces)("%s: same keys, no empty values, same placeholders", (file) => {
    const reference = load(REFERENCE, file);
    const translated = load(lang, file);

    expect(Object.keys(translated).sort()).toEqual(Object.keys(reference).sort());
    for (const [key, text] of Object.entries(translated)) {
      expect(text.trim(), `${lang}/${file}: ${key} is empty`).not.toBe("");
      expect(placeholders(text), `${lang}/${file}: ${key} placeholders`).toEqual(
        placeholders(reference[key])
      );
    }
  });
});
