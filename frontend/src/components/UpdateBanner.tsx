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

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowUpCircle, ExternalLink, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface UpdateCheck {
  current: string;
  latest: string | null;
  update_available: boolean;
  release_url: string;
}

const DISMISSED_KEY = "update_banner_dismissed";

function readDismissed(): string | null {
  try {
    return localStorage.getItem(DISMISSED_KEY);
  } catch {
    return null;
  }
}

// Hint for admins that a newer openDox release exists (GET /settings/update-check/).
// Dismissing is remembered per version, so the next release shows it again.
export function UpdateBanner() {
  const { t } = useTranslation("updateCheck");
  const { user, authFetch } = useAuth();
  const [info, setInfo] = useState<UpdateCheck | null>(null);
  const [dismissed, setDismissed] = useState<string | null>(readDismissed);
  const privileged = user?.role === "admin" || user?.role === "demo_viewer";

  useEffect(() => {
    if (!privileged) return;
    let alive = true;
    authFetch("/api/v1/settings/update-check/")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (alive) setInfo(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [privileged, authFetch]);

  if (!privileged || !info?.update_available || !info.latest) return null;
  if (dismissed === info.latest) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, info.latest as string);
    } catch {
      // storage blocked: the banner just hides until the next load
    }
    setDismissed(info.latest);
  };

  return (
    <div
      role="status"
      className="flex items-center gap-3 border-b border-border bg-primary/10 px-4 py-2 text-sm shrink-0"
    >
      <ArrowUpCircle className="h-4 w-4 shrink-0 text-primary" />
      <span className="flex-1 min-w-0">
        {t("message", { latest: info.latest, current: info.current })}{" "}
        <a
          href={info.release_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
        >
          {t("viewRelease")}
          <ExternalLink className="h-3 w-3" />
        </a>
      </span>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t("dismiss")}
        className="shrink-0 rounded p-1 hover:bg-primary/10"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default UpdateBanner;
