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

import { describe, it, expect, vi, afterEach } from "vitest";
import { act } from "react";
import { renderHook } from "@testing-library/react";
import { useIsMobile } from "@/hooks/use-mobile";

function setInnerWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    configurable: true,
    value: width,
  });
}

function mockMatchMedia() {
  let changeHandler: (() => void) | undefined;
  const mql = {
    matches: false,
    media: "",
    addEventListener: vi.fn((_event: string, handler: () => void) => {
      changeHandler = handler;
    }),
    removeEventListener: vi.fn(),
  };
  window.matchMedia = vi.fn().mockReturnValue(mql);
  return {
    mql,
    triggerChange: () => {
      changeHandler?.();
    },
  };
}

describe("useIsMobile", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns true when the viewport is narrower than the mobile breakpoint", () => {
    setInnerWidth(500);
    mockMatchMedia();

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(true);
  });

  it("returns false when the viewport is at or above the mobile breakpoint", () => {
    setInnerWidth(1024);
    mockMatchMedia();

    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);
  });

  it("registers a change listener on the media query list", () => {
    setInnerWidth(1024);
    const { mql } = mockMatchMedia();

    renderHook(() => useIsMobile());

    expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 767px)");
    expect(mql.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("updates the value when the media query change handler fires", () => {
    setInnerWidth(1024);
    const { triggerChange } = mockMatchMedia();

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    act(() => {
      setInnerWidth(400);
      triggerChange();
    });

    expect(result.current).toBe(true);
  });

  it("removes the change listener on unmount", () => {
    setInnerWidth(1024);
    const { mql } = mockMatchMedia();

    const { unmount } = renderHook(() => useIsMobile());
    unmount();

    expect(mql.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });
});
