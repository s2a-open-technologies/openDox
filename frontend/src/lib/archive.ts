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

export const UNKNOWN_DATE_KEY = "unknown";

export interface ArchiveDateGroup<T> {
  key: string;
  label: string;
  count: number;
  recordings: T[];
}

const GERMAN_TIMESTAMP_RE =
  /^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:,?\s+)(\d{1,2}):(\d{2})(?::(\d{2}))?$/;

const pad2 = (value: number): string => value.toString().padStart(2, "0");

export const parseRecordTimestamp = (timestamp: string): Date | null => {
  const match = GERMAN_TIMESTAMP_RE.exec(timestamp.trim());
  if (match) {
    const [, day, month, year, hour, minute, second] = match;
    return new Date(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      second ? Number(second) : 0
    );
  }
  const fallback = new Date(timestamp);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
};

const toDateKey = (date: Date): string =>
  `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;

const startOfDay = (date: Date): number =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

export const formatDateLabel = (key: string): string => {
  if (key === UNKNOWN_DATE_KEY) return "Unbekanntes Datum";
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const diffDays = Math.round(
    (startOfDay(new Date()) - startOfDay(date)) / 86_400_000
  );
  if (diffDays === 0) return "Heute";
  if (diffDays === 1) return "Gestern";
  return `${pad2(day)}.${pad2(month)}.${year}`;
};

export const formatRecordTime = (timestamp: string): string => {
  const date = parseRecordTimestamp(timestamp);
  if (!date) return "";
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
};

export const groupRecordingsByDate = <T extends { timestamp: string }>(
  recordings: T[]
): ArchiveDateGroup<T>[] => {
  const buckets = new Map<string, T[]>();
  for (const recording of recordings) {
    const date = parseRecordTimestamp(recording.timestamp);
    const key = date ? toDateKey(date) : UNKNOWN_DATE_KEY;
    const bucket = buckets.get(key);
    if (bucket) {
      bucket.push(recording);
    } else {
      buckets.set(key, [recording]);
    }
  }
  return [...buckets.entries()]
    .sort(([aKey], [bKey]) => {
      if (aKey === UNKNOWN_DATE_KEY) return 1;
      if (bKey === UNKNOWN_DATE_KEY) return -1;
      return bKey.localeCompare(aKey);
    })
    .map(([key, bucket]) => ({
      key,
      label: formatDateLabel(key),
      count: bucket.length,
      recordings: [...bucket].sort((a, b) => {
        const aTime = parseRecordTimestamp(a.timestamp)?.getTime() ?? 0;
        const bTime = parseRecordTimestamp(b.timestamp)?.getTime() ?? 0;
        return bTime - aTime;
      }),
    }));
};