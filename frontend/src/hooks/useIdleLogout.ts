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

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { isRecordingActive, lastActivity, markActivity } from "@/lib/sessionActivity";

const ACTIVITY_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart"] as const;
// localStorage is written at most this often while the user is busy.
const MARK_THROTTLE_MS = 5_000;
const CHECK_INTERVAL_MS = 15_000;

/**
 * Log out after the admin-configured idle time (session-config,
 * 0 = never). Activity in any tab counts, and a running recording keeps the
 * session alive however long it takes.
 */
export function useIdleLogout(): void {
  const { isAuthenticated, authFetch, expireSession } = useAuth();
  const [timeoutMinutes, setTimeoutMinutes] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) return;
    authFetch("/api/v1/settings/session-config/")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.idle_timeout_minutes === "number") {
          setTimeoutMinutes(data.idle_timeout_minutes);
        }
      })
      .catch(() => {
        // Keep the previous value; the server is checked again on next login.
      });
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || timeoutMinutes <= 0) return;
    const limitMs = timeoutMinutes * 60_000;

    const isIdle = () => {
      const last = lastActivity();
      return last > 0 && Date.now() - last >= limitMs;
    };
    // A page reopened after a long break (laptop lid, closed tab) ends here.
    if (isIdle() && !isRecordingActive()) {
      expireSession("idle");
      return;
    }
    markActivity();

    let lastMark = Date.now();
    const onActivity = () => {
      const now = Date.now();
      if (now - lastMark >= MARK_THROTTLE_MS) {
        lastMark = now;
        markActivity(now);
      }
    };
    ACTIVITY_EVENTS.forEach((name) =>
      window.addEventListener(name, onActivity, { passive: true })
    );

    const timer = window.setInterval(() => {
      if (isRecordingActive()) {
        markActivity();
      } else if (isIdle()) {
        expireSession("idle");
      }
    }, CHECK_INTERVAL_MS);

    return () => {
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, onActivity));
      window.clearInterval(timer);
    };
  }, [isAuthenticated, timeoutMinutes]);
}
