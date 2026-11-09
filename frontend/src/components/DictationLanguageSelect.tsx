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
import { Info } from "lucide-react";
import { languageName } from "@/lib/languageName";
import type { TranslationAvailability } from "@/hooks/useTranslationAvailability";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface DictationLanguageSelectProps {
  availability: TranslationAvailability;
  /** "" = the instance language (no translation). */
  value: string;
  onChange: (value: string) => void;
  /** Show the hint when the live preview cannot follow the language. */
  liveHint?: boolean;
  disabled?: boolean;
  id?: string;
}

const INSTANCE = "__instance__";

// "Diktiersprache": only rendered while translation is released for the user.
export function DictationLanguageSelect({
  availability,
  value,
  onChange,
  liveHint = false,
  disabled = false,
  id = "dictation-language",
}: DictationLanguageSelectProps) {
  const { t, i18n } = useTranslation("record");
  if (!availability.available || availability.languages.length === 0) return null;

  const name = (code: string) => languageName(code, i18n.language);
  const target = availability.target_language;
  const noLive = liveHint && value !== "" && !availability.live_languages.includes(value);

  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-medium">{t("dictationLanguage.label")}</label>
      <Select
        value={value || INSTANCE}
        onValueChange={(val) => onChange(val === INSTANCE ? "" : val)}
        disabled={disabled}
      >
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={INSTANCE}>{t("dictationLanguage.instance", { language: name(target) })}</SelectItem>
          {availability.languages.map((code) => (
            <SelectItem key={code} value={code}>{name(code)}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {value !== "" && (
        <p className="text-xs text-muted-foreground">
          {t("dictationLanguage.translatedInto", { language: name(target) })}
        </p>
      )}
      {noLive && (
        <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {t("dictationLanguage.noLivePreview")}
        </p>
      )}
    </div>
  );
}
