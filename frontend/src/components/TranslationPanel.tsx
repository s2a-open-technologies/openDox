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

import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

export interface TranslationSegment {
  source: string;
  target: string;
  paragraph: number;
  missing_numbers: string[];
  extra_numbers: string[];
}

interface TranslationPanelProps {
  segments: TranslationSegment[];
  /** Edited targets by sentence index (unsaved). */
  edits: Record<number, string>;
  onEdit: (index: number, target: string) => void;
  /** Editing only after the review confirmation, like the transcript. */
  editable: boolean;
}

const flagged = (s: TranslationSegment) => s.missing_numbers.length > 0 || s.extra_numbers.length > 0;

// Sentence pairs: translation on top (editable), the dictated original below.
// Pairs whose numbers differ are highlighted, so the reviewer checks them first.
export function TranslationPanel({ segments, edits, onEdit, editable }: TranslationPanelProps) {
  const { t } = useTranslation("transcript");
  const flaggedCount = segments.filter(flagged).length;

  if (segments.length === 0) {
    return <p className="text-muted-foreground italic">{t("translation.none")}</p>;
  }

  return (
    <div className="flex flex-col gap-3 min-h-0">
      {flaggedCount > 0 && (
        <p className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {t("translation.flaggedSummary", { count: flaggedCount })}
        </p>
      )}
      <ol className="flex flex-col gap-3 overflow-y-auto min-h-0 pr-1">
        {segments.map((segment, index) => {
          const isFlagged = flagged(segment);
          const value = edits[index] ?? segment.target;
          return (
            <li
              key={index}
              data-flagged={isFlagged || undefined}
              className={`rounded-md border p-3 ${isFlagged ? "border-amber-400 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40" : ""}`}
            >
              <Textarea
                value={value}
                aria-label={t("translation.sentenceLabel", { n: index + 1 })}
                readOnly={!editable}
                onChange={(e) => onEdit(index, e.target.value)}
                onCopy={(e) => { if (!editable) e.preventDefault(); }}
                onCut={(e) => { if (!editable) e.preventDefault(); }}
                rows={Math.max(1, Math.ceil(value.length / 80))}
                className={`min-h-0 resize-none border-0 bg-transparent p-0 text-base shadow-none focus-visible:ring-0${!editable ? " select-none" : ""}`}
              />
              <p dir="auto" className="mt-1 text-xs text-muted-foreground">{segment.source}</p>
              {isFlagged && (
                <p className="mt-1 text-xs font-medium text-amber-700 dark:text-amber-400">
                  {[
                    segment.missing_numbers.length > 0 &&
                      t("translation.missingNumbers", { numbers: segment.missing_numbers.join(", ") }),
                    segment.extra_numbers.length > 0 &&
                      t("translation.extraNumbers", { numbers: segment.extra_numbers.join(", ") }),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
