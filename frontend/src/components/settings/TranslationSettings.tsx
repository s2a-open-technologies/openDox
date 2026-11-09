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
import { useEffect, useState } from "react";
import { Languages, Plus } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { apiErrorMessage } from "@/lib/apiError";
import { languageName } from "@/lib/languageName";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type Access = "all" | "selected";

interface TranslationConfig {
  enabled: boolean;
  access: Access;
  languages: string[];
  target_language: string;
}

// Offered as checkboxes; any other ISO 639-1 code can be added by hand.
const SUGGESTED = ["ru", "uk", "pl", "ro", "bg", "sr", "hr", "bs", "sq", "cs", "hu", "tr", "ar", "fa", "en", "fr", "es", "it", "el"];

const EMPTY: TranslationConfig = { enabled: false, access: "selected", languages: [], target_language: "de" };

// Diktat in einer anderen Sprache, übersetzt in die Sprache der Instanz.
export function TranslationSettings({ readOnly = false }: { readOnly?: boolean }) {
  const { t, i18n } = useTranslation(["translation", "common"]);
  const { authFetch } = useAuth();
  const [config, setConfig] = useState<TranslationConfig>(EMPTY);
  const [extra, setExtra] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch("/api/v1/settings/translation/")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setConfig(data))
      .catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const target = config.target_language;
  const name = (code: string) => languageName(code, i18n.language);
  const options = Array.from(new Set([...SUGGESTED, ...config.languages])).filter((code) => code !== target);

  const toggle = (code: string, checked: boolean) =>
    setConfig({
      ...config,
      languages: checked ? [...config.languages, code] : config.languages.filter((c) => c !== code),
    });

  const addExtra = () => {
    const code = extra.trim().toLowerCase();
    if (!/^[a-z]{2}$/.test(code)) {
      toast.error(t("invalidCode"));
      return;
    }
    if (code !== target && !config.languages.includes(code)) {
      setConfig({ ...config, languages: [...config.languages, code] });
    }
    setExtra("");
  };

  const save = async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/settings/translation/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: config.enabled, access: config.access, languages: config.languages }),
      });
      if (res.ok) {
        setConfig(await res.json());
        toast.success(t("saved"));
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(apiErrorMessage(err, t("common:saveFailed")));
      }
    } catch {
      toast.error(t("common:connectionError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="translation-enabled" className="text-base">{t("enabled")}</Label>
            <p className="text-sm text-muted-foreground">{t("purposeHint")}</p>
          </div>
          <Switch
            id="translation-enabled"
            checked={config.enabled}
            disabled={readOnly}
            onCheckedChange={(checked) => setConfig({ ...config, enabled: checked })}
          />
        </div>

        <div className="flex items-center gap-3 rounded-md border p-3 text-sm">
          <Languages className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span>
            {t("target", { language: name(target) })}{" "}
            <span className="text-muted-foreground">{t("targetHint")}</span>
          </span>
        </div>

        <div className="space-y-2">
          <Label>{t("access")}</Label>
          <div className="space-y-2">
            {(["selected", "all"] as Access[]).map((access) => (
              <label key={access} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="translation-access"
                  className="mt-1"
                  checked={config.access === access}
                  disabled={readOnly}
                  onChange={() => setConfig({ ...config, access })}
                />
                <span>
                  {t(`accessOptions.${access}`)}
                  <span className="block text-xs text-muted-foreground">{t(`accessHints.${access}`)}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label>{t("languages")}</Label>
          <p className="text-xs text-muted-foreground">{t("languagesHint")}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {options.map((code) => (
              <label key={code} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={config.languages.includes(code)}
                  disabled={readOnly}
                  onCheckedChange={(checked) => toggle(code, checked === true)}
                />
                <span>{name(code)}</span>
                <span className="text-xs text-muted-foreground">{code}</span>
              </label>
            ))}
          </div>
          <div className="flex gap-2 pt-2">
            <Input
              value={extra}
              maxLength={2}
              placeholder={t("otherCode")}
              aria-label={t("otherCode")}
              className="w-60"
              disabled={readOnly}
              onChange={(e) => setExtra(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addExtra();
                }
              }}
            />
            <Button type="button" variant="outline" size="icon" aria-label={t("add")} disabled={readOnly} onClick={addExtra}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={save} disabled={loading || readOnly}>
            {loading ? t("common:saving") : t("common:save")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
