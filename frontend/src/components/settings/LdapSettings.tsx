import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface LdapSettingsData {
    id?: number;
    server_host: string;
    server_port: number;
    use_ssl: boolean;
    base_dn: string;
    user_dn: string;
    bind_user_dn: string;
    bind_user_password: string;
}

const LdapSettings = () => {
    const { authFetch } = useAuth();
    const [isSSL, setIsSSL] = useState(false);
    const [settings, setSettings] = useState<LdapSettingsData>({
        server_host: '',
        server_port: 636,
        use_ssl: false,
        base_dn: '',
        user_dn: '',
        bind_user_dn: '',
        bind_user_password: '',
    });
    const [loading, setLoading] = useState(false);

    // Fetch settings on mount (mocked for now as we just restored api)
    // In real app, useEffect to fetch from /api/settings/ldap-settings/

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await authFetch('/api/v1/settings/ldap-settings/', {
                method: 'PUT',
                body: JSON.stringify(settings),
            });
            // Show success toast
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
                                onChange={e => setSettings({ ...settings, server_port: parseInt(e.target.value) })}
                            />
                        </div>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Switch
                            id="use-ssl"
                            checked={settings.use_ssl}
                            onCheckedChange={(checked) => {
                                setSettings({ ...settings, use_ssl: checked });
                                setIsSSL(checked);
                            }}
                        />
                        <Label htmlFor="use-ssl">SSL (LDAPS) verwenden</Label>
                    </div>
                    {isSSL && (
                        <div className="space-y-2">
                            <Label>Zertifikatsdateiname</Label>
                            <Input
                                value={(settings as any).cert_filename || ''}
                                onChange={e => setSettings({ ...settings, cert_filename: e.target.value } as any)}
                                placeholder="cert.pem"
                            />
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
