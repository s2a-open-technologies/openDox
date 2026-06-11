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
import { Pencil, Plus, Trash2, Shield } from 'lucide-react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';

interface UserData {
    id: number;
    name: string;
    is_active: boolean;
    is_superuser: boolean;
}

const UserSettings = () => {
    const { authFetch } = useAuth();
    const [users, setUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingUser, setEditingUser] = useState<UserData | null>(null);
    const [formData, setFormData] = useState({
        name: '',
        password: '',
        is_active: true,
        is_superuser: false,
    });

    const fetchUsers = async () => {
        try {
            const res = await authFetch('/api/v1/auth/users');
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            }
        } catch (error) {
            console.error('Failed to fetch users:', error);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const openCreate = () => {
        setEditingUser(null);
        setFormData({ name: '', password: '', is_active: true, is_superuser: false });
        setDialogOpen(true);
    };

    const openEdit = (user: UserData) => {
        setEditingUser(user);
        setFormData({
            name: user.name,
            password: '',
            is_active: user.is_active,
            is_superuser: user.is_superuser,
        });
        setDialogOpen(true);
    };

    const handleSubmit = async () => {
        setLoading(true);
        try {
            const url = editingUser
                ? `/api/v1/auth/users/${editingUser.id}`
                : '/api/v1/auth/users';
            const method = editingUser ? 'PUT' : 'POST';

            const body: any = {
                name: formData.name,
                is_active: formData.is_active,
                is_superuser: formData.is_superuser,
            };
            if (formData.password) body.password = formData.password;

            const res = await authFetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json();
                alert(err.detail || 'Operation fehlgeschlagen');
                return;
            }

            setDialogOpen(false);
            await fetchUsers();
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Moechten Sie diesen Benutzer wirklich loeschen?')) return;
        try {
            const res = await authFetch(`/api/v1/auth/users/${id}`, { method: 'DELETE' });
            if (res.ok) {
                await fetchUsers();
            } else {
                const err = await res.json();
                alert(err.detail || 'Loeschung fehlgeschlagen');
            }
        } catch (error) {
            console.error('Failed to delete user:', error);
        }
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Benutzerliste</CardTitle>
                        <CardDescription>Verwalten Sie lokale Benutzerkonten</CardDescription>
                    </div>
                    <Button onClick={openCreate} className="flex items-center gap-2">
                        <Plus className="w-4 h-4" />
                        Benutzer anlegen
                    </Button>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        {users.map((user) => (
                            <div
                                key={user.id}
                                className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                            >
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">{user.name}</span>
                                        {user.is_superuser && (
                                            <Shield className="w-4 h-4 text-primary" />
                                        )}
                                    </div>
                                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                                        <span className={user.is_active ? 'text-green-600' : 'text-red-500'}>
                                            {user.is_active ? 'Aktiv' : 'Inaktiv'}
                                        </span>
                                        {user.is_superuser && (
                                            <span className="text-primary">Admin</span>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={() => openEdit(user)}
                                    >
                                        <Pencil className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="text-destructive hover:text-destructive"
                                        onClick={() => handleDelete(user.id)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                        {users.length === 0 && (
                            <div className="text-center text-muted-foreground py-8">
                                Keine Benutzer vorhanden
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-[450px]">
                    <DialogHeader>
                        <DialogTitle>
                            {editingUser ? 'Benutzer bearbeiten' : 'Neuen Benutzer anlegen'}
                        </DialogTitle>
                        <DialogDescription>
                            {editingUser
                                ? 'Bearbeiten Sie die Benutzerdaten. Passwort leer lassen um es nicht zu aendern.'
                                : 'Legen Sie einen neuen lokalen Benutzer an.'}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Benutzername</Label>
                            <Input
                                value={formData.name}
                                onChange={e => setFormData({ ...formData, name: e.target.value })}
                                placeholder="z.B. dr.mueller"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Passwort {editingUser && '(leer = unveraendert)'}</Label>
                            <Input
                                type="password"
                                value={formData.password}
                                onChange={e => setFormData({ ...formData, password: e.target.value })}
                                placeholder="••••••••"
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label htmlFor="is-active">Aktiv</Label>
                            <Switch
                                id="is-active"
                                checked={formData.is_active}
                                onCheckedChange={checked => setFormData({ ...formData, is_active: checked })}
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label htmlFor="is-superuser">Administrator</Label>
                            <Switch
                                id="is-superuser"
                                checked={formData.is_superuser}
                                onCheckedChange={checked => setFormData({ ...formData, is_superuser: checked })}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDialogOpen(false)}>Abbrechen</Button>
                        <Button onClick={handleSubmit} disabled={loading}>
                            {loading ? 'Speichern...' : (editingUser ? 'Aktualisieren' : 'Anlegen')}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default UserSettings;
