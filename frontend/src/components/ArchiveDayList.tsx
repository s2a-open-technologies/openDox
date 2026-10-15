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

import { useTranslation } from "react-i18next";
import { CalendarDays, FileAudio, MoreHorizontal, RotateCcw, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDateLabel, formatRecordTime, groupRecordingsByDate } from "@/lib/archive";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import type { Recording } from "@/pages/Dashboard";

interface ArchiveDayListProps {
  recordings: Recording[];
  selectedDate: string | null;
  onSelectRecording: (recording: Recording) => void;
  onUnarchiveRecording?: (id: string) => void;
  onDeleteRecording?: (id: string) => void;
  onBackToDates: () => void;
}

const ArchiveDayList = ({
  recordings,
  selectedDate,
  onSelectRecording,
  onUnarchiveRecording,
  onDeleteRecording,
  onBackToDates,
}: ArchiveDayListProps) => {
  const { t } = useTranslation("record");
  const groups = groupRecordingsByDate(recordings);
  const dayGroup = selectedDate
    ? groups.find((group) => group.key === selectedDate)
    : undefined;

  if (!dayGroup) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8 bg-background">
        <div className="w-12 h-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
          <CalendarDays className="w-6 h-6 text-muted-foreground" />
        </div>
        <div className="space-y-1 mt-4">
          <h2 className="text-xl font-semibold">{t("archive.title")}</h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            {t("archive.selectDate")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-auto p-8 bg-background">
      <Card className="w-full overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/50 dark:bg-zinc-900/50">
          <Button
            variant="ghost"
            size="icon"
            onClick={onBackToDates}
            title={t("archive.backToDates")}
            className="shrink-0"
          >
            <CalendarDays className="w-5 h-5" />
          </Button>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">
              {formatDateLabel(dayGroup.key)}
            </h2>
            <p className="text-xs text-muted-foreground">
              {t("archive.count", { count: dayGroup.count })}
            </p>
          </div>
        </div>

        <div className="p-2">
          {dayGroup.recordings.map((recording) => (
          <div
            key={recording.id}
            className="group relative w-full rounded-lg transition-all duration-200 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <button
              onClick={() => onSelectRecording(recording)}
              className="w-full text-left px-4 py-3 pr-10"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center bg-zinc-100 dark:bg-zinc-800 text-muted-foreground">
                  <FileAudio className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate text-foreground">
                    {recording.title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatRecordTime(recording.timestamp)}
                  </p>
                </div>
              </div>
            </button>

            <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 max-md:opacity-100 transition-opacity">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-zinc-200 dark:hover:bg-zinc-700">
                    <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onUnarchiveRecording?.(recording.id)}>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    {t("archive.restore")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => onDeleteRecording?.(recording.id)}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {t("archive.delete")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        ))}
        </div>
      </Card>
    </div>
  );
};

export default ArchiveDayList;