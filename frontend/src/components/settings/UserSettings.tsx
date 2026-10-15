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

import { apiErrorMessage } from '@/lib/apiError';
import { useTranslation } from 'react-i18next';
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Pencil, Plus, Trash2, Shield } from 'lucide-react';
import { toast } from 'sonner';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';

type Role = 'admin' | 'moderator' | 'demo_viewer' | 'user';

interface UserData {
    id: number;
    name: string;
    is_active: boolean;
    role: Role;
}

const UserSettings = ({ readOnly = false }: { readOnly?: boolean }) => {
    const { t } = useTranslation(['users', 'common']);
    const { authFetch } = useAuth();
    const [users, setUsers] = useState<UserData[]>([]);
    const [loading, setLoading] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingUser, setEditingUser] = useState<UserData | null>(null);
    const [formData, setFormData] = useState<{
        name: string;
        password: string;
        is_active: boolean;
        role: Role;
    }>({
        name: '',
        password: '',
        is_active: true,
        role: 'user',
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
        setFormData({ name: '', password: '', is_active: true, role: 'user' });
        setDialogOpen(true);
    };

    const openEdit = (user: UserData) => {
        setEditingUser(user);
        setFormData({
            name: user.name,
            password: '',
            is_active: user.is_active,
            role: user.role,
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

            const body: { name: string; is_active: boolean; role: Role; password?: string } = {
                name: formData.name,
                is_active: formData.is_active,
                role: formData.role,
            };
            if (formData.password) body.password = formData.password;

            const res = await authFetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const err = await res.json();
                toast.error(apiErrorMessage(err, t('operationFailed')));
                return;
            }

            toast.success(editingUser ? t('updated') : t('created'));
            setDialogOpen(false);
            await fetchUsers();
        } catch (error) {
            console.error(error);
            toast.error(t('common:connectionError'));
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm(t('confirmDelete'))) return;
        try {
            const res = await authFetch(`/api/v1/auth/users/${id}`, { method: 'DELETE' });
            if (res.ok) {
                toast.success(t('deleted'));
                await fetchUsers();
            } else {
                const err = await res.json();
                toast.error(apiErrorMessage(err, t('deleteFailed')));
            }
        } catch (error) {
            console.error('Failed to delete user:', error);
            toast.error(t('common:connectionError'));
        }
    };

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>{t('listTitle')}</CardTitle>
                        <CardDescription>{t('listDescription')}</CardDescription>
                    </div>
                    <Button onClick={openCreate} disabled={readOnly} className="flex items-center gap-2">
                        <Plus className="w-4 h-4" />
                        {t('create')}
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
                                        {user.role !== 'user' && (
                                            <Shield className="w-4 h-4 text-primary" />
                                        )}
                                    </div>
                                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                                        <span className={user.is_active ? 'text-green-600' : 'text-red-500'}>
                                            {user.is_active ? t('active') : t('inactive')}
                                        </span>
                                        <span className={user.role === 'admin' ? 'text-primary' : ''}>
                                            {t(`common:roles.${user.role}`)}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        disabled={readOnly}
                                        onClick={() => openEdit(user)}
                                    >
                                        <Pencil className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="text-destructive hover:text-destructive"
                                        disabled={readOnly}
                                        onClick={() => handleDelete(user.id)}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                        {users.length === 0 && (
                            <div className="text-center text-muted-foreground py-8">
                                {t('empty')}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-[450px]">
                    <DialogHeader>
                        <DialogTitle>
                            {editingUser ? t('dialog.editTitle') : t('dialog.createTitle')}
                        </DialogTitle>
                        <DialogDescription>
                            {editingUser
                                ? t('dialog.editDescription')
                                : t('dialog.createDescription')}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>{t('dialog.username')}</Label>
                            <Input
                                value={formData.name}
                                onChange={e => setFormData({ ...formData, name: e.target.value })}
                                placeholder={t('dialog.usernamePlaceholder')}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>{t('dialog.password')} {editingUser && t('dialog.passwordUnchanged')}</Label>
                            <Input
                                type="password"
                                value={formData.password}
                                onChange={e => setFormData({ ...formData, password: e.target.value })}
                                placeholder="••••••••"
                            />
                        </div>
                        <div className="flex items-center justify-between">
                            <Label htmlFor="is-active">{t('dialog.isActive')}</Label>
                            <Switch
                                id="is-active"
                                checked={formData.is_active}
                                onCheckedChange={checked => setFormData({ ...formData, is_active: checked })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>{t('dialog.role')}</Label>
                            <Select
                                value={formData.role}
                                onValueChange={(v: Role) => setFormData({ ...formData, role: v })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="admin">{t('common:roles.admin')}</SelectItem>
                                    <SelectItem value="moderator">{t('common:roles.moderator')}</SelectItem>
                                    <SelectItem value="demo_viewer">{t('common:roles.demo_viewer')}</SelectItem>
                                    <SelectItem value="user">{t('common:roles.user')}</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDialogOpen(false)}>{t('common:cancel')}</Button>
                        <Button onClick={handleSubmit} disabled={loading || readOnly}>
                            {loading ? t('common:saving') : (editingUser ? t('dialog.update') : t('dialog.add'))}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default UserSettings;
