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

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// Every locales/<lang>/<namespace>.json is picked up automatically.
const modules = import.meta.glob<Record<string, unknown>>("./locales/*/*.json", {
  eager: true,
  import: "default",
});
const resources: Record<string, Record<string, Record<string, unknown>>> = {};
for (const [path, content] of Object.entries(modules)) {
  const [, lang, file] = path.match(/\.\/locales\/([^/]+)\/([^/]+)\.json$/) ?? [];
  if (!lang) continue;
  (resources[lang] ??= {})[file] = content;
}
const namespaces = Object.keys(resources.de ?? {});

// To add a language: create locales/<code>/*.json (the glob above finds it),
// add it here, and add the code to UI_LANGUAGES in
// backend/components/models/user_model.py.
export const SUPPORTED_LANGUAGES = [
  { code: "de", label: "Deutsch" },
  { code: "en", label: "English" },
] as const;

export type UiLanguage = (typeof SUPPORTED_LANGUAGES)[number]["code"];

export const DEFAULT_LANGUAGE: UiLanguage = "de";
const STORAGE_KEY = "ui_language";

export const isSupportedLanguage = (code: unknown): code is UiLanguage =>
  SUPPORTED_LANGUAGES.some((l) => l.code === code);

// Before login there is no user record: last chosen language (localStorage),
// then the browser language, then German.
const detectInitialLanguage = (): UiLanguage => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isSupportedLanguage(stored)) return stored;
  } catch {
    // localStorage unavailable (private mode etc.) — fall through
  }
  const browser = typeof navigator !== "undefined" ? navigator.language : "";
  const short = browser.slice(0, 2).toLowerCase();
  return isSupportedLanguage(short) ? short : DEFAULT_LANGUAGE;
};

i18n.use(initReactI18next).init({
  resources,
  lng: detectInitialLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: "common",
  ns: namespaces,
  interpolation: { escapeValue: false }, // React already escapes
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
});
document.documentElement.lang = i18n.language;

/** Switch the UI language and remember it for the pre-login screens. */
export const applyUiLanguage = async (code: UiLanguage): Promise<void> => {
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // ignore — persistence is a convenience only
  }
  await i18n.changeLanguage(code);
};

export default i18n;
