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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Activity } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';

const SystemSettings = () => {
    const { authFetch } = useAuth();
    const [status, setStatus] = useState<'online' | 'offline' | 'checking'>('checking');
    const [lastChecked, setLastChecked] = useState<Date | null>(null);

    const checkHealth = async () => {
        try {
            // Using fetch since health is public
            const response = await fetch('/api/health', { cache: 'no-store' });
            if (response.ok) {
                setStatus('online');
            } else {
                setStatus('offline');
            }
        } catch (error) {
            setStatus('offline');
        } finally {
            setLastChecked(new Date());
        }
    };

    useEffect(() => {
        checkHealth();
        const interval = setInterval(checkHealth, 10000); // Check every 10 seconds
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Systemstatus</CardTitle>
                    <CardDescription>Überblick über den aktuellen Serverstatus</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 border rounded-md">
                        <div className="flex items-center gap-4">
                            <div className="p-2 bg-muted rounded-full">
                                <Activity className="w-6 h-6 text-foreground" />
                            </div>
                            <div>
                                <h4 className="font-medium">Backend Server</h4>
                                <p className="text-sm text-muted-foreground">
                                    {lastChecked ? `Zuletzt geprüft: ${lastChecked.toLocaleTimeString()}` : 'Prüfe...'}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className={`w-3 h-3 rounded-full ${status === 'online' ? 'bg-green-500' :
                                status === 'offline' ? 'bg-red-500' : 'bg-yellow-500'
                                }`} />
                            <span className="font-medium">
                                {status === 'online' ? 'Online' :
                                    status === 'offline' ? 'Nicht erreichbar' : 'Prüfung...'}
                            </span>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

export default SystemSettings;
