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
import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

// Automatische Abmeldung der Weboberfläche nach Inaktivität (session-config).
export function SessionSettings({ readOnly = false }: { readOnly?: boolean }) {
  const { t } = useTranslation(["system", "common"]);
  const { authFetch } = useAuth();
  const [minutes, setMinutes] = useState(30);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch("/api/v1/settings/session-config/")
      .then((res) => res.json())
      .then((data) => {
        if (typeof data.idle_timeout_minutes === "number") setMinutes(data.idle_timeout_minutes);
      })
      .catch(console.error);
  }, []);

  const save = async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/settings/session-config/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idle_timeout_minutes: minutes }),
      });
      if (res.ok) {
        const saved = await res.json();
        setMinutes(saved.idle_timeout_minutes);
        toast.success(t("session.saved"));
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
        <CardTitle>{t("session.title")}</CardTitle>
        <CardDescription>{t("session.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="session-idle-timeout">{t("session.idleTimeout")}</Label>
          <Input
            id="session-idle-timeout"
            type="number"
            min={0}
            max={1440}
            value={minutes}
            disabled={readOnly}
            onChange={(e) => setMinutes(Math.min(1440, Math.max(0, parseInt(e.target.value) || 0)))}
          />
          <p className="text-xs text-muted-foreground">{t("session.idleTimeoutHint")}</p>
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
