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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface AudioSettings {
  audio_download_enabled: boolean;
  audio_bitrate: string;
  audio_sample_rate: number;
  audio_format: string;
}

type AudioSettingsResponse = Partial<AudioSettings>;

const BITRATE_FORMATS = new Set(["mp3", "ogg"]);

export function AudioConfig({ readOnly = false }: { readOnly?: boolean }) {
  const { t, i18n } = useTranslation(["audio", "common"]);
  const { authFetch } = useAuth();
  const [config, setConfig] = useState<AudioSettings>({
    audio_download_enabled: true,
    audio_bitrate: "64k",
    audio_sample_rate: 16000,
    audio_format: "mp3",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch('/api/v1/settings/audio-settings/')
      .then(res => res.json())
      .then((data: AudioSettingsResponse) => {
        setConfig({
          audio_download_enabled: data.audio_download_enabled ?? true,
          audio_bitrate: data.audio_bitrate ?? "64k",
          audio_sample_rate: data.audio_sample_rate ?? 16000,
          audio_format: data.audio_format ?? "mp3",
        });
      })
      .catch(console.error);
  }, []);

  const updateField = (field: keyof AudioSettings, value: boolean | string | number) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const saveConfig = async () => {
    setLoading(true);
    try {
      const res = await authFetch('/api/v1/settings/audio-settings/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        toast.success(t('saved'));
      } else {
        toast.error(t('common:saveFailed'));
      }
    } catch {
      toast.error(t('common:connectionError'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('title')}</CardTitle>
        <CardDescription>
          {t('description')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-3">
          <Switch
            id="audio-enabled"
            checked={config.audio_download_enabled}
            disabled={readOnly}
            onCheckedChange={(checked) => updateField('audio_download_enabled', checked)}
          />
          <Label htmlFor="audio-enabled">{t('enabled')}</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="audio-format">{t('format')}</Label>
          <select
            id="audio-format"
            value={config.audio_format}
            disabled={readOnly}
            onChange={(e) => updateField('audio_format', e.target.value)}
            className="w-full px-3 py-2 border rounded-md bg-background"
          >
            <option value="mp3">{t('formats.mp3')}</option>
            <option value="ogg">{t('formats.ogg')}</option>
            <option value="flac">{t('formats.flac')}</option>
            <option value="wav">{t('formats.wav')}</option>
          </select>
        </div>
        {BITRATE_FORMATS.has(config.audio_format) && (
          <div className="space-y-2">
            <Label htmlFor="audio-bitrate">{t('bitrate')}</Label>
            <select
              id="audio-bitrate"
              value={config.audio_bitrate}
              disabled={readOnly}
              onChange={(e) => updateField('audio_bitrate', e.target.value)}
              className="w-full px-3 py-2 border rounded-md bg-background"
            >
              <option value="32k">{t('bitrateOption', { kbit: 32, size: (0.4).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="48k">{t('bitrateOption', { kbit: 48, size: (0.6).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="64k">{t('bitrateOption', { kbit: 64, size: (0.8).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="96k">{t('bitrateOption', { kbit: 96, size: (1.2).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="128k">{t('bitrateOption', { kbit: 128, size: (1.5).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="160k">{t('bitrateOption', { kbit: 160, size: (1.9).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="192k">{t('bitrateOption', { kbit: 192, size: (2.3).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="256k">{t('bitrateOption', { kbit: 256, size: (3.0).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
              <option value="320k">{t('bitrateOption', { kbit: 320, size: (3.8).toLocaleString(i18n.language, { minimumFractionDigits: 1 }) })}</option>
            </select>
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="audio-sample-rate">{t('sampleRate')}</Label>
          <select
            id="audio-sample-rate"
            value={config.audio_sample_rate.toString()}
            disabled={readOnly}
            onChange={(e) => updateField('audio_sample_rate', parseInt(e.target.value))}
            className="w-full px-3 py-2 border rounded-md bg-background"
          >
            <option value="16000">{t('rates.16000')}</option>
            <option value="22050">{t('rates.22050')}</option>
            <option value="44100">{t('rates.44100')}</option>
          </select>
        </div>
        <p className="text-xs text-muted-foreground">
          {t('note')}
        </p>
        <div className="pt-4 flex justify-end">
          <Button onClick={saveConfig} disabled={loading || readOnly}>
            {loading ? t('common:saving') : t('common:save')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}