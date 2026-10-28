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

// Shared state for the idle logout (hooks/useIdleLogout.ts). The last activity
// lives in localStorage so that all open tabs share it: working in one tab
// keeps the others logged in too.

const LAST_ACTIVITY_KEY = "last_activity";

let memoryLastActivity = 0;
let recordingActive = false;

/** Note user activity now. */
export function markActivity(now: number = Date.now()): void {
  memoryLastActivity = now;
  try {
    localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
  } catch {
    // Storage blocked (private mode): the in-memory value still works per tab.
  }
}

/** Time of the last activity in any tab, in ms since the epoch; 0 = none yet. */
export function lastActivity(): number {
  try {
    const stored = Number(localStorage.getItem(LAST_ACTIVITY_KEY));
    if (stored > 0) return Math.max(stored, memoryLastActivity);
  } catch {
    // fall through
  }
  return memoryLastActivity;
}

/** Forget the activity time (on logout), so a stale value never carries over. */
export function clearActivity(): void {
  memoryLastActivity = 0;
  try {
    localStorage.removeItem(LAST_ACTIVITY_KEY);
  } catch {
    // ignore
  }
}

/** The recorder reports here while it records; no idle logout meanwhile. */
export function setRecordingActive(active: boolean): void {
  recordingActive = active;
}

export function isRecordingActive(): boolean {
  return recordingActive;
}
