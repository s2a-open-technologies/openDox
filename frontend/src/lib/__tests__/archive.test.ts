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

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  formatDateLabel,
  formatRecordTime,
  groupRecordingsByDate,
  parseRecordTimestamp,
  UNKNOWN_DATE_KEY,
} from "@/lib/archive";

interface Item {
  timestamp: string;
  title: string;
}

describe("parseRecordTimestamp", () => {
  it("parses the backend's zero-padded DD.MM.YYYY HH:MM:SS format", () => {
    expect(parseRecordTimestamp("23.09.2026 14:30:05")).toEqual(
      new Date(2026, 8, 23, 14, 30, 5)
    );
  });

  it("parses toLocaleString('de-DE') output with comma and without zero padding", () => {
    expect(parseRecordTimestamp("1.3.2026, 7:05:12")).toEqual(
      new Date(2026, 2, 1, 7, 5, 12)
    );
  });

  it("parses timestamps without a seconds part", () => {
    expect(parseRecordTimestamp("22.09.2026 10:00")).toEqual(
      new Date(2026, 8, 22, 10, 0, 0)
    );
  });

  it("falls back to Date parsing for ISO timestamps", () => {
    // new Date("2024-01-01") is parsed as UTC midnight, so compare against the
    // same constructor output instead of a local-time expectation.
    expect(parseRecordTimestamp("2024-01-01")).toEqual(new Date("2024-01-01"));
  });

  it("returns null for unparsable strings", () => {
    expect(parseRecordTimestamp("irgendwas")).toBeNull();
    expect(parseRecordTimestamp("")).toBeNull();
  });
});

describe("groupRecordingsByDate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 23, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("groups recordings by day, newest first, and counts entries", () => {
    const items: Item[] = [
      { timestamp: "22.09.2026 10:00:00", title: "gestern-b" },
      { timestamp: "23.09.2026 09:00:00", title: "heute-a" },
      { timestamp: "23.09.2026 08:00:00", title: "heute-b" },
      { timestamp: "21.09.2026 12:00:00", title: "vor3" },
    ];
    const groups = groupRecordingsByDate(items);
    expect(groups.map((g) => g.label)).toEqual(["Heute", "Gestern", "21.09.2026"]);
    expect(groups.map((g) => g.count)).toEqual([2, 1, 1]);
    expect(groups[0].recordings.map((r) => r.title)).toEqual(["heute-a", "heute-b"]);
    expect(groups[0].key).toBe("2026-09-23");
  });

  it("sorts recordings within a day by time descending", () => {
    const items: Item[] = [
      { timestamp: "23.09.2026 09:30:00", title: "spaeter" },
      { timestamp: "23.09.2026 08:15:00", title: "frueher" },
    ];
    const groups = groupRecordingsByDate(items);
    expect(groups[0].recordings.map((r) => r.title)).toEqual(["spaeter", "frueher"]);
  });

  it("collects unparsable timestamps into a trailing 'Unbekanntes Datum' group", () => {
    const items: Item[] = [
      { timestamp: "kaputt", title: "ohne-datum" },
      { timestamp: "23.09.2026 09:00:00", title: "heute" },
    ];
    const groups = groupRecordingsByDate(items);
    expect(groups).toHaveLength(2);
    expect(groups[1].key).toBe(UNKNOWN_DATE_KEY);
    expect(groups[1].label).toBe("Unbekanntes Datum");
    expect(groups[1].recordings[0].title).toBe("ohne-datum");
  });
});

describe("formatDateLabel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 23, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("labels today as 'Heute'", () => {
    expect(formatDateLabel("2026-09-23")).toBe("Heute");
  });

  it("labels yesterday as 'Gestern'", () => {
    expect(formatDateLabel("2026-09-22")).toBe("Gestern");
  });

  it("labels older days as DD.MM.YYYY", () => {
    expect(formatDateLabel("2026-09-21")).toBe("21.09.2026");
    expect(formatDateLabel("2025-01-02")).toBe("02.01.2025");
  });

  it("labels the unknown key", () => {
    expect(formatDateLabel(UNKNOWN_DATE_KEY)).toBe("Unbekanntes Datum");
  });
});

describe("formatRecordTime", () => {
  it("extracts HH:MM from a backend timestamp", () => {
    expect(formatRecordTime("23.09.2026 14:30:05")).toBe("14:30");
  });

  it("returns an empty string for unparsable timestamps", () => {
    expect(formatRecordTime("kaputt")).toBe("");
  });
});