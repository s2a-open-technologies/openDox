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
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

interface OidcSettingsData {
    id?: number;
    enabled: boolean;
    provider_url: string;
    client_id: string;
    client_secret: string;
    scopes: string;
    group_claim: string;
    admin_groups: string;
    moderator_groups: string;
    username_claim: string;
}

type OidcSettingsResponse = Partial<OidcSettingsData>;

const OidcSettings = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { t } = useTranslation(['oidc', 'common']);
    const { authFetch } = useAuth();
    const [settings, setSettings] = useState<OidcSettingsData>({
        enabled: false,
        provider_url: '',
        client_id: '',
        client_secret: '',
        scopes: 'openid email profile',
        group_claim: 'groups',
        admin_groups: '',
        moderator_groups: '',
        username_claim: 'preferred_username',
    });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        authFetch('/api/v1/settings/oidc-settings/')
            .then(res => res.json())
            .then((data: OidcSettingsResponse) => {
                if (data && data.provider_url !== undefined) {
                    setSettings({
                        enabled: data.enabled ?? false,
                        provider_url: data.provider_url || '',
                        client_id: data.client_id || '',
                        client_secret: data.client_secret || '',
                        scopes: data.scopes || 'openid email profile',
                        group_claim: data.group_claim || 'groups',
                        admin_groups: data.admin_groups || '',
                        moderator_groups: data.moderator_groups || '',
                        username_claim: data.username_claim || 'preferred_username',
                    });
                }
            })
            .catch(console.error);
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await authFetch('/api/v1/settings/oidc-settings/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
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
            <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="flex items-center gap-3">
                        <Switch
                            id="oidc-enabled"
                            checked={settings.enabled}
                            disabled={readOnly}
                            onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
                        />
                        <Label htmlFor="oidc-enabled">{t('enable')}</Label>
                    </div>

                    <div className="space-y-2">
                        <Label>{t('providerUrl')}</Label>
                        <Input
                            value={settings.provider_url}
                            disabled={readOnly}
                            onChange={e => setSettings({ ...settings, provider_url: e.target.value })}
                            placeholder="https://keycloak.example.com/realms/myrealm"
                        />
                        <p className="text-xs text-muted-foreground">
                            {t('providerUrlHint')}
                        </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>{t('clientId')}</Label>
                            <Input
                                value={settings.client_id}
                                disabled={readOnly}
                                onChange={e => setSettings({ ...settings, client_id: e.target.value })}
                                placeholder="opendox"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>{t('clientSecret')}</Label>
                            <Input
                                type="password"
                                disabled={readOnly}
                                value={settings.client_secret}
                                onChange={e => setSettings({ ...settings, client_secret: e.target.value })}
                                placeholder="••••••••"
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label>{t('scopes')}</Label>
                        <Input
                            value={settings.scopes}
                            disabled={readOnly}
                            onChange={e => setSettings({ ...settings, scopes: e.target.value })}
                            placeholder="openid email profile"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>{t('usernameClaim')}</Label>
                        <Input
                            value={settings.username_claim}
                            disabled={readOnly}
                            onChange={e => setSettings({ ...settings, username_claim: e.target.value })}
                            placeholder="preferred_username"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>{t('groupClaim')}</Label>
                            <Input
                                value={settings.group_claim}
                                disabled={readOnly}
                                onChange={e => setSettings({ ...settings, group_claim: e.target.value })}
                                placeholder="groups"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>{t('adminGroups')}</Label>
                            <Input
                                value={settings.admin_groups}
                                disabled={readOnly}
                                onChange={e => setSettings({ ...settings, admin_groups: e.target.value })}
                                placeholder="opendox-admin"
                            />
                            <p className="text-xs text-muted-foreground">
                                {t('adminGroupsHint')}
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>{t('moderatorGroups')}</Label>
                            <Input
                                value={settings.moderator_groups}
                                disabled={readOnly}
                                onChange={e => setSettings({ ...settings, moderator_groups: e.target.value })}
                                placeholder="opendox-moderator"
                            />
                            <p className="text-xs text-muted-foreground">
                                {t('moderatorGroupsHint')}
                            </p>
                        </div>
                    </div>

                    <div className="pt-2">
                        <Button type="submit" disabled={loading || readOnly}>{t('common:save')}</Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
};

export default OidcSettings;