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
import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

// Gleiche Schlüssel wie die settings.json des Desktop-Clients
// (opendox-client: internal/clientpolicy.Settings).
interface ClientSettings {
  clipboard_exclude_from_history: boolean;
  clipboard_clear_after_seconds: number;
  insert_allowlist: string[];
  dictation_mic_mode: "hold" | "toggle";
  live_view: boolean;
}

const DEFAULTS: ClientSettings = {
  clipboard_exclude_from_history: true,
  clipboard_clear_after_seconds: 30,
  insert_allowlist: [],
  dictation_mic_mode: "hold",
  live_view: true,
};

export function ClientConfig({ readOnly = false }: { readOnly?: boolean }) {
  const { t } = useTranslation(["clients", "common"]);
  const { authFetch } = useAuth();
  const [config, setConfig] = useState<ClientSettings>(DEFAULTS);
  // Allow-List als Freitext (ein Programm pro Zeile), erst beim Speichern zerlegt.
  const [allowlistText, setAllowlistText] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch("/api/v1/settings/client-config/")
      .then(res => res.json())
      .then((data: Partial<ClientSettings>) => {
        const loaded = { ...DEFAULTS, ...data };
        setConfig(loaded);
        setAllowlistText(loaded.insert_allowlist.join("\n"));
      })
      .catch(console.error);
  }, []);

  const updateField = <K extends keyof ClientSettings>(field: K, value: ClientSettings[K]) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/settings/client-config/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...config, insert_allowlist: allowlistText.split("\n") }),
      });
      if (res.ok) {
        const saved: ClientSettings = await res.json();
        setConfig(saved);
        setAllowlistText(saved.insert_allowlist.join("\n"));
        toast.success(t("saved"));
      } else {
        toast.error(t("common:saveFailed"));
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
        <CardTitle>{t("config.title")}</CardTitle>
        <CardDescription>{t("config.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-3">
          <Switch
            id="client-live-view"
            checked={config.live_view}
            disabled={readOnly}
            onCheckedChange={(checked) => updateField("live_view", checked)}
          />
          <Label htmlFor="client-live-view">{t("config.liveView")}</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="client-mic-mode">{t("config.micMode")}</Label>
          <select
            id="client-mic-mode"
            value={config.dictation_mic_mode}
            disabled={readOnly}
            onChange={(e) => updateField("dictation_mic_mode", e.target.value as ClientSettings["dictation_mic_mode"])}
            className="w-full px-3 py-2 border rounded-md bg-background"
          >
            <option value="hold">{t("config.micModes.hold")}</option>
            <option value="toggle">{t("config.micModes.toggle")}</option>
          </select>
        </div>
        <div className="flex items-center gap-3">
          <Switch
            id="client-clipboard-exclude"
            checked={config.clipboard_exclude_from_history}
            disabled={readOnly}
            onCheckedChange={(checked) => updateField("clipboard_exclude_from_history", checked)}
          />
          <Label htmlFor="client-clipboard-exclude">{t("config.clipboardExclude")}</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="client-clipboard-clear">{t("config.clipboardClear")}</Label>
          <Input
            id="client-clipboard-clear"
            type="number"
            min={0}
            value={config.clipboard_clear_after_seconds}
            disabled={readOnly}
            onChange={(e) => updateField("clipboard_clear_after_seconds", Math.max(0, parseInt(e.target.value) || 0))}
          />
          <p className="text-xs text-muted-foreground">{t("config.clipboardClearHint")}</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="client-allowlist">{t("config.allowlist")}</Label>
          <Textarea
            id="client-allowlist"
            rows={4}
            value={allowlistText}
            disabled={readOnly}
            placeholder="medistar.exe"
            onChange={(e) => setAllowlistText(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">{t("config.allowlistHint")}</p>
        </div>
        <p className="text-xs text-muted-foreground">{t("config.note")}</p>
        <div className="pt-4 flex justify-end">
          <Button onClick={saveConfig} disabled={loading || readOnly}>
            {loading ? t("common:saving") : t("common:save")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
