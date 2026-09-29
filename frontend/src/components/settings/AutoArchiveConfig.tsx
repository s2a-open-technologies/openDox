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

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface AutoArchiveSettings {
  auto_archive_enabled: boolean;
  auto_archive_days: number;
}

type AutoArchiveSettingsResponse = Partial<AutoArchiveSettings>;

export function AutoArchiveConfig({ readOnly = false }: { readOnly?: boolean }) {
  const { authFetch } = useAuth();
  const [config, setConfig] = useState<AutoArchiveSettings>({
    auto_archive_enabled: false,
    auto_archive_days: 90,
  });
  // '' while the user is editing the day input; number otherwise.
  const [daysInput, setDaysInput] = useState<string | number>("90");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch('/api/v1/settings/audio-settings/')
      .then(res => res.json())
      .then((data: AutoArchiveSettingsResponse) => {
        const enabled = data.auto_archive_enabled ?? false;
        const days = data.auto_archive_days ?? 90;
        setConfig({ auto_archive_enabled: enabled, auto_archive_days: days });
        setDaysInput(days);
      })
      .catch(console.error);
  }, []);

  // Persist-on-save semantics like the other admin cards: local edits first,
  // numeric validation gate before the API call.
  const daysInvalid =
    typeof daysInput !== "number" ||
    !Number.isInteger(daysInput) ||
    daysInput < 1 ||
    daysInput > 3650;

  const saveConfig = async () => {
    if (daysInvalid) {
      toast.error('Frist muss eine ganze Zahl zwischen 1 und 3650 sein');
      return;
    }
    setLoading(true);
    try {
      const res = await authFetch('/api/v1/settings/audio-settings/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        toast.success('Auto-Archivierung gespeichert');
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Speichern fehlgeschlagen');
      }
    } catch {
      toast.error('Verbindungsfehler');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Auto-Archivierung</CardTitle>
        <CardDescription>
          Archiviert Aufnahmen automatisch nach Ablauf der Frist (bezogen auf
          die Uhrzeit der Aufnahme) — dieselbe Wirkung wie „Archivieren“ im
          Zeilenmenü. Archivierte Aufnahmen verschwinden aus „Aktuell“ und sind
          über den Archiv-Tab jederzeit wiederherstellbar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-3">
          <Switch
            id="auto-archive-enabled"
            checked={config.auto_archive_enabled}
            disabled={readOnly}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({ ...prev, auto_archive_enabled: checked }))
            }
          />
          <Label htmlFor="auto-archive-enabled">Automatisch archivieren</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="auto-archive-days">Frist in Tagen</Label>
          <Input
            id="auto-archive-days"
            type="number"
            min={1}
            max={3650}
            step={1}
            inputMode="numeric"
            value={daysInput}
            disabled={readOnly}
            onChange={(e) => {
              const raw = e.target.value;
              setDaysInput(raw === "" ? "" : Math.max(0, parseInt(raw, 10) || 0));
              const n = parseInt(raw, 10);
              if (raw !== "" && Number.isInteger(n)) {
                setConfig((prev) => ({ ...prev, auto_archive_days: n }));
              }
            }}
          />
          {daysInvalid && (
            <p className="text-xs text-destructive">
              Bitte eine ganze Zahl zwischen 1 und 3650 eingeben.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Prüflauf alle 6 Stunden; geänderte Werte greifen ohne Neustart.
            Aufnahmen, die manuell aus dem Archiv zurückgeholt wurden, bleiben
            unberührt, bis das Fristende erneut erreicht ist.
          </p>
        </div>
        <div className="pt-4 flex justify-end">
          <Button
            onClick={saveConfig}
            disabled={loading || readOnly || daysInvalid}
          >
            {loading ? 'Speichern...' : 'Speichern'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}