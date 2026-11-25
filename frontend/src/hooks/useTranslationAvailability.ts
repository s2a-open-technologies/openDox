/*
  openDox - Medical transcription platform
  Copyright (C) 2026  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";

export interface TranslationAvailability {
  available: boolean;
  languages: string[];
  target_language: string;
  live_languages: string[];
}

const UNAVAILABLE: TranslationAvailability = {
  available: false,
  languages: [],
  target_language: "de",
  live_languages: [],
};

// Whether the current user may dictate in another language, and which ones
// (GET /settings/translation/me). Loaded on mount; off on any error. `reload`
// refetches, so changes made by an admin show up without a re-login.
export function useTranslationAvailability(): [TranslationAvailability, () => void] {
  const { authFetch } = useAuth();
  const [availability, setAvailability] = useState<TranslationAvailability>(UNAVAILABLE);
  const authFetchRef = useRef(authFetch);
  authFetchRef.current = authFetch;
  const alive = useRef(true);

  const reload = useCallback(() => {
    authFetchRef.current("/api/v1/settings/translation/me")
      .then((res) => (res.ok ? res.json() : UNAVAILABLE))
      .then((data) => {
        if (alive.current) setAvailability({ ...UNAVAILABLE, ...data });
      })
      .catch(() => {
        if (alive.current) setAvailability(UNAVAILABLE);
      });
  }, []);

  useEffect(() => {
    alive.current = true;
    reload();
    return () => {
      alive.current = false;
    };
  }, [reload]);

  return [availability, reload];
}
