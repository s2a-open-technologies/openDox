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

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/AuthContext';
import { apiErrorMessage } from '@/lib/apiError';

interface Retention {
  personal_days: number | null;
  global_enabled: boolean;
  global_days: number;
}

const URL = '/api/v1/settings/my-retention/';

/** The user's own automatic deletion period, capped by the global limit. */
export function MyRetention() {
  const { t } = useTranslation(['retention', 'common']);
  const { authFetch } = useAuth();
  const [retention, setRetention] = useState<Retention | null>(null);
  // '' = no personal period.
  const [daysInput, setDaysInput] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    authFetch(URL)
      .then((res) => res.json())
      .then((data: Retention) => {
        setRetention(data);
        setDaysInput(data.personal_days == null ? '' : String(data.personal_days));
      })
      .catch(console.error);
    // authFetch is recreated on every AuthProvider render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const max = retention?.global_enabled ? retention.global_days : 3650;
  const days = daysInput === '' ? null : Number(daysInput);
  const invalid = days !== null && (!Number.isInteger(days) || days < 1 || days > max);

  const save = async () => {
    setSaving(true);
    try {
      const res = await authFetch(URL, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personal_days: days }),
      });
      if (res.ok) {
        setRetention(await res.json());
        toast.success(t('saved'));
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(apiErrorMessage(err, t('common:saveFailed')));
      }
    } catch {
      toast.error(t('common:connectionError'));
    } finally {
      setSaving(false);
    }
  };

  if (!retention) return null;

  return (
    <div className="space-y-4 max-w-md">
      <p className="text-sm">
        {retention.global_enabled
          ? t('globalLimit', { days: retention.global_days })
          : t('noGlobalLimit')}
      </p>
      <div className="space-y-2">
        <Label htmlFor="my-retention-days">{t('label')}</Label>
        <Input
          id="my-retention-days"
          type="number"
          min={1}
          max={max}
          step={1}
          inputMode="numeric"
          placeholder={t('placeholder')}
          value={daysInput}
          onChange={(e) => setDaysInput(e.target.value)}
        />
        {invalid && <p className="text-xs text-destructive">{t('invalid', { max })}</p>}
        <p className="text-xs text-muted-foreground">{t('hint')}</p>
      </div>
      <div className="flex justify-end">
        <Button onClick={save} disabled={saving || invalid}>
          {saving ? t('common:saving') : t('common:save')}
        </Button>
      </div>
    </div>
  );
}
