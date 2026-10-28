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

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAuth } from "@/contexts/AuthContext";
import { useIdleLogout } from "@/hooks/useIdleLogout";
import { markActivity, setRecordingActive, clearActivity } from "@/lib/sessionActivity";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);

function setup(idleTimeoutMinutes: number) {
  const expireSession = vi.fn();
  const authFetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ idle_timeout_minutes: idleTimeoutMinutes }),
  } as Response);
  mockedUseAuth.mockReturnValue({
    isAuthenticated: true,
    authFetch,
    expireSession,
  } as unknown as ReturnType<typeof useAuth>);
  return { expireSession };
}

// Let the session-config fetch resolve and the effect re-run.
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useIdleLogout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    clearActivity();
    setRecordingActive(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("logs out after the configured idle time", async () => {
    const { expireSession } = setup(1);
    renderHook(() => useIdleLogout());
    await flush();

    act(() => vi.advanceTimersByTime(45_000));
    expect(expireSession).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(30_000));
    expect(expireSession).toHaveBeenCalledWith("idle");
  });

  it("activity resets the timer", async () => {
    const { expireSession } = setup(1);
    renderHook(() => useIdleLogout());
    await flush();

    act(() => vi.advanceTimersByTime(50_000));
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown"));
    });
    act(() => vi.advanceTimersByTime(30_000));

    expect(expireSession).not.toHaveBeenCalled();
  });

  it("never logs out while recording", async () => {
    const { expireSession } = setup(1);
    renderHook(() => useIdleLogout());
    await flush();

    setRecordingActive(true);
    act(() => vi.advanceTimersByTime(10 * 60_000));
    expect(expireSession).not.toHaveBeenCalled();

    // After the recording the full idle time starts again.
    setRecordingActive(false);
    act(() => vi.advanceTimersByTime(30_000));
    expect(expireSession).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(60_000));
    expect(expireSession).toHaveBeenCalledWith("idle");
  });

  it("does nothing when the timeout is 0", async () => {
    const { expireSession } = setup(0);
    renderHook(() => useIdleLogout());
    await flush();

    act(() => vi.advanceTimersByTime(24 * 60 * 60_000));
    expect(expireSession).not.toHaveBeenCalled();
  });

  it("ends a session reopened after a long break", async () => {
    markActivity(Date.now() - 2 * 60 * 60_000);
    const { expireSession } = setup(30);
    renderHook(() => useIdleLogout());
    await flush();

    expect(expireSession).toHaveBeenCalledWith("idle");
  });
});
