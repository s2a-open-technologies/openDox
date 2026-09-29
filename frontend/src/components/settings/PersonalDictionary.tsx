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

import { useTranslation } from 'react-i18next';
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

interface PersonalGlossaryResponse {
    personal_glossary: string | null;
}

const PersonalDictionary = () => {
    const { t } = useTranslation(['dictionary', 'common']);
    const { authFetch } = useAuth();
    const [glossary, setGlossary] = useState('');
    const [loading, setLoading] = useState(false);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        authFetch('/api/v1/settings/my-dictionary/')
            .then(async res => {
                if (!res.ok) {
                    throw new Error('Loading failed');
                }
                const data: PersonalGlossaryResponse = await res.json();
                setGlossary(data.personal_glossary ?? '');
                setLoaded(true);
            })
            .catch(error => {
                console.error(error);
                toast.error(t('loadFailed'));
            });
    }, []);

    const save = async () => {
        setLoading(true);
        try {
            const res = await authFetch('/api/v1/settings/my-dictionary/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ personal_glossary: glossary || null }),
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
            <CardContent className="space-y-4">
                <Textarea
                    value={glossary}
                    onChange={e => setGlossary(e.target.value)}
                    placeholder={t('placeholder')}
                    className="min-h-[120px]"
                    disabled={!loaded}
                />
                <p className="text-xs text-muted-foreground">
                    {t('hint')}
                </p>
                <Button onClick={save} disabled={loading || !loaded}>
                    {loading ? t('common:saving') : t('common:save')}
                </Button>
            </CardContent>
        </Card>
    );
};

export default PersonalDictionary;
