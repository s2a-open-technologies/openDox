/*
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, Check, FileBadge } from 'lucide-react';

interface LdapSettingsData {
    id?: number;
    server_host: string;
    server_port: number;
    use_ssl: boolean;
    base_dn: string;
    user_dn: string;
    bind_user_dn: string;
    bind_user_password: string;
    cert_filename: string;
}

const LdapSettings = () => {
    const { authFetch } = useAuth();
    const [settings, setSettings] = useState<LdapSettingsData>({
        server_host: '',
        server_port: 389,
        use_ssl: false,
        base_dn: '',
        user_dn: '',
        bind_user_dn: '',
        bind_user_password: '',
        cert_filename: '',
    });
    const [loading, setLoading] = useState(false);
    const [certFile, setCertFile] = useState<File | null>(null);
    const [certUploading, setCertUploading] = useState(false);

    // Load settings on mount
    useEffect(() => {
        authFetch('/api/v1/settings/ldap-settings/')
            .then(res => res.json())
            .then((data: any) => {
                if (data && data.server_host !== undefined) {
                    setSettings({
                        server_host: data.server_host || '',
                        server_port: data.server_port || 389,
                        use_ssl: data.use_ssl || false,
                        base_dn: data.base_dn || '',
                        user_dn: data.user_dn || '',
                        bind_user_dn: data.bind_user_dn || '',
                        bind_user_password: data.bind_user_password || '',
                        cert_filename: data.cert_filename || '',
                    });
                }
            })
            .catch(console.error);
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await authFetch('/api/v1/settings/ldap-settings/', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            });
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleTest = async () => {
        setLoading(true);
        try {
            const res = await authFetch('/api/v1/settings/ldap-settings/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            });
            const data = await res.json();
            alert(data.message);
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleSSLChange = (checked: boolean) => {
        setSettings(prev => ({
            ...prev,
            use_ssl: checked,
            server_port: checked ? 636 : 389,
        }));
    };

    const handleCertUpload = async () => {
        if (!certFile) return;

        setCertUploading(true);
        const formData = new FormData();
        formData.append('file', certFile);

        try {
            const res = await authFetch('/api/v1/settings/ldap-settings/upload-cert/', {
                method: 'POST',
                body: formData,
            });
            const data = await res.json();
            if (data.filename) {
                setSettings(prev => ({ ...prev, cert_filename: data.filename }));
                setCertFile(null);
            }
        } catch (error) {
            console.error('Cert upload failed:', error);
        } finally {
            setCertUploading(false);
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>LDAP Konfiguration</CardTitle>
                <CardDescription>Verbinden Sie Ihre Benutzerverwaltung</CardDescription>
            </CardHeader>
            <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Server Host</Label>
                            <Input
                                value={settings.server_host}
                                onChange={e => setSettings({ ...settings, server_host: e.target.value })}
                                placeholder="ldaps.example.com"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Port</Label>
                            <Input
                                type="number"
                                value={settings.server_port}
                                onChange={e => setSettings({ ...settings, server_port: parseInt(e.target.value) || 389 })}
                            />
                        </div>
                    </div>

                    <div className="flex items-center space-x-2">
                        <Switch
                            id="use-ssl"
                            checked={settings.use_ssl}
                            onCheckedChange={handleSSLChange}
                        />
                        <Label htmlFor="use-ssl">SSL (LDAPS) verwenden</Label>
                    </div>

                    {settings.use_ssl && (
                        <div className="space-y-2 p-4 border rounded-md bg-muted/30">
                            <Label>Zertifikat hochladen</Label>
                            <div className="flex items-center gap-2">
                                <input
                                    type="file"
                                    accept=".pem,.crt,.cer"
                                    onChange={(e) => setCertFile(e.target.files?.[0] || null)}
                                    className="flex-1 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary file:text-primary-foreground hover:file:bg-primary/90"
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={handleCertUpload}
                                    disabled={!certFile || certUploading}
                                >
                                    {certUploading ? 'Lädt...' : <><Upload className="w-4 h-4 mr-1" /> Upload</>}
                                </Button>
                            </div>
                            {settings.cert_filename && (
                                <div className="flex items-center gap-1 text-sm text-green-600">
                                    <FileBadge className="w-4 h-4" />
                                    <span>{settings.cert_filename}</span>
                                    <Check className="w-4 h-4 ml-1" />
                                </div>
                            )}
                        </div>
                    )}

                    <div className="space-y-2">
                        <Label>Base DN</Label>
                        <Input
                            value={settings.base_dn}
                            onChange={e => setSettings({ ...settings, base_dn: e.target.value })}
                            placeholder="dc=example,dc=com"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>User DN Pattern (uid or sAMAccountName)</Label>
                        <Input
                            value={settings.user_dn}
                            onChange={e => setSettings({ ...settings, user_dn: e.target.value })}
                            placeholder="uid"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Bind User DN</Label>
                        <Input
                            value={settings.bind_user_dn}
                            onChange={e => setSettings({ ...settings, bind_user_dn: e.target.value })}
                            placeholder="cn=admin,dc=example,dc=com"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Bind User Password</Label>
                        <Input
                            type="password"
                            value={settings.bind_user_password}
                            onChange={e => setSettings({ ...settings, bind_user_password: e.target.value })}
                        />
                    </div>

                    <div className="flex space-x-2 pt-4">
                        <Button type="submit" disabled={loading}>Speichern</Button>
                        <Button type="button" variant="outline" onClick={handleTest} disabled={loading}>Verbindung testen</Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
};

export default LdapSettings;
