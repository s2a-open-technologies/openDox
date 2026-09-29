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

import { useTranslation } from "react-i18next";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import { formatRecordTimestamp, groupRecordingsByDate } from "@/lib/archive";
import { FileAudio, MoreHorizontal, Archive, Trash2, RotateCcw, Library, Radio, Upload, CalendarDays } from "lucide-react";
import UserDropdown from "@/components/UserDropdown";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { Recording } from "@/pages/Dashboard";

interface SidebarProps {
  recordings: Recording[];
  onSelectRecording: (recording: Recording) => void;
  selectedId?: string;
  activeSessionId?: string;
  onDeleteRecording?: (id: string) => void;
  onArchiveRecording?: (id: string) => void;
  onUnarchiveRecording?: (id: string) => void;
  showArchived?: boolean;
  onToggleArchived?: (show: boolean) => void;
  selectedArchiveDate?: string | null;
  onSelectArchiveDate?: (dateKey: string | null) => void;
  onUploadClick?: () => void;
  showUploadButton?: boolean;
  mobileOpen?: boolean;
  onMobileOpenChange?: (open: boolean) => void;
}

const Sidebar = ({
  recordings,
  onSelectRecording,
  selectedId,
  activeSessionId,
  onDeleteRecording,
  onArchiveRecording,
  onUnarchiveRecording,
  showArchived = false,
  onToggleArchived,
  selectedArchiveDate = null,
  onSelectArchiveDate,
  onUploadClick,
  showUploadButton = true,
  mobileOpen = false,
  onMobileOpenChange,
}: SidebarProps) => {
  const { t } = useTranslation("record");
  // Closing the drawer after selecting a recording is mobile-only UX; harmless no-op on desktop.
  const handleSelectRecording = (recording: Recording) => {
    onSelectRecording(recording);
    onMobileOpenChange?.(false);
  };

  const dateGroups = showArchived ? groupRecordingsByDate(recordings) : [];

  const content = (
    <>
      <div className="p-4 border-b border-border z-10 relative bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex flex-col gap-2">
        <div className="flex items-center justify-center w-full">
          <Logo className="h-16 w-full px-2" />
        </div>
      </div>

      <div className="px-2 pt-2 flex gap-2 ">
        <Button
          variant={!showArchived ? "secondary" : "ghost"}
          className={cn("flex-1", !showArchived && "bg-zinc-100 dark:bg-zinc-800 font-medium")}
          onClick={() => onToggleArchived?.(false)}
          title={t("sidebar.current")}
        >
          <Library className="w-4 h-4" />
        </Button>
        <Button
          variant={showArchived ? "secondary" : "ghost"}
          className={cn("flex-1", showArchived && "bg-zinc-100 dark:bg-zinc-800 font-medium")}
          onClick={() => onToggleArchived?.(true)}
          title={t("sidebar.archive")}
        >
          <Archive className="w-4 h-4" />
        </Button>
        {showUploadButton && (
          <Button
            variant="ghost"
            className="flex-1"
            onClick={() => onUploadClick?.()}
            title={t("sidebar.upload")}
          >
            <Upload className="w-4 h-4" />
          </Button>
        )}
      </div>

      <ScrollArea className="flex-1 min-h-0 py-3 px-2">
        {showArchived ? (
          <div className="space-y-1">
            {dateGroups.length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                <FileAudio className="w-8 h-8 mx-auto mb-2" />
                <p className="text-sm">{t("sidebar.noArchived")}</p>
              </div>
            ) : (
              dateGroups.map((group) => {
                const isSelected = selectedArchiveDate === group.key;
                return (
                  <button
                    key={group.key}
                    onClick={() => onSelectArchiveDate?.(group.key)}
                    className={cn(
                      "w-full rounded-lg px-4 py-3 text-left transition-all duration-200 flex items-center gap-3",
                      isSelected
                        ? "bg-blue-50 dark:bg-zinc-800/80 ring-1 ring-primary/20"
                        : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    )}
                  >
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                      isSelected
                        ? "bg-primary/10 text-primary"
                        : "bg-zinc-100 dark:bg-zinc-800 text-muted-foreground"
                    )}>
                      <CalendarDays className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-sm font-semibold truncate",
                        isSelected ? "text-primary" : "text-foreground"
                      )}>
                        {group.label}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {t("archive.count", { count: group.count })}
                      </p>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        ) : (
          <div className="space-y-1">
            {recordings.length === 0 ? (
              <div className="p-6 text-center text-muted-foreground">
                <FileAudio className="w-8 h-8 mx-auto mb-2" />
                <p className="text-sm">{t("sidebar.none")}</p>
              </div>
            ) : (
            recordings.map((recording) => {
              const isActive = activeSessionId && recording.id === activeSessionId;
              const isSelected = selectedId === recording.id;
              return (
                <div
                  key={recording.id}
                  className={cn(
                    "group relative w-full rounded-lg transition-all duration-200",
                    isSelected
                      ? "bg-blue-50 dark:bg-zinc-800/80 ring-1 ring-primary/20"
                      : isActive
                        ? "bg-red-50 dark:bg-red-900/20 ring-1 ring-red-300 dark:ring-red-700"
                        : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  )}
                >
                  <button
                    onClick={() => handleSelectRecording(recording)}
                    className="w-full text-left px-4 py-3 pr-10"
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                        isSelected
                          ? "bg-primary/10 text-primary"
                          : isActive
                            ? "bg-red-100 text-red-500 animate-pulse"
                            : "bg-zinc-100 dark:bg-zinc-800 text-muted-foreground"
                      )}>
                        {isActive ? <Radio className="w-4 h-4" /> : <FileAudio className="w-4 h-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={cn(
                          "text-sm font-semibold truncate transition-colors",
                          isSelected ? "text-primary" : isActive ? "text-red-600 dark:text-red-400" : "text-foreground"
                        )}>
                          {recording.title}
                        </p>
                        <div className="flex items-center gap-2">
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatRecordTimestamp(recording.timestamp)}
                          </p>
                          {isActive && (
                            <span className="text-[10px] font-medium text-red-500 px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 rounded-full mt-0.5">
                              {t("sidebar.active")}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>

                  {!isActive && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 max-md:opacity-100 transition-opacity">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-zinc-200 dark:hover:bg-zinc-700">
                            <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {showArchived ? (
                            <DropdownMenuItem onClick={() => onUnarchiveRecording?.(recording.id)}>
                              <RotateCcw className="w-4 h-4 mr-2" />
                              {t("archive.restore")}
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem onClick={() => onArchiveRecording?.(recording.id)}>
                              <Archive className="w-4 h-4 mr-2" />
                              {t("sidebar.archiveAction")}
                            </DropdownMenuItem>
                          )}
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
                  )}
                </div>
              );
            })
            )}
          </div>
        )}
      </ScrollArea>
      <div className="p-2 border-t border-border">
        <UserDropdown />
      </div>
    </>
  );

  return (
    <>
      {/* Desktop: static, always-visible sidebar */}
      <aside className="hidden md:flex w-80 bg-background flex-col border-r border-border h-dvh">
        {content}
      </aside>

      {/* Mobile: off-canvas drawer, opened via the trigger button in Dashboard's mobile top bar */}
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-80 h-dvh p-0 flex flex-col">
          {content}
        </SheetContent>
      </Sheet>
    </>
  );
};

export default Sidebar;
