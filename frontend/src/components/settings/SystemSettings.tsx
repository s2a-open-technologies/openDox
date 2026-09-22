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

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Activity } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

type ServiceStatus = 'online' | 'offline' | 'disabled';

interface ServiceHealth {
    name: string;
    status: ServiceStatus;
}

const statusDotClass: Record<ServiceStatus, string> = {
    online: 'bg-green-500',
    offline: 'bg-red-500',
    disabled: 'bg-gray-400',
};

const statusLabel: Record<ServiceStatus, string> = {
    online: 'Online',
    offline: 'Nicht erreichbar',
    disabled: 'Deaktiviert',
};

const SystemSettings = () => {
    const { authFetch } = useAuth();
    const [services, setServices] = useState<ServiceHealth[]>([]);
    const [lastChecked, setLastChecked] = useState<Date | null>(null);
    const [version, setVersion] = useState<string | null>(null);

    useEffect(() => {
        fetch('/api/version')
            .then((res) => res.json())
            .then((data) => setVersion(data.version))
            .catch(() => setVersion(null));
    }, []);

    const checkHealth = async () => {
        try {
            const response = await authFetch('/api/v1/settings/services-health/');
            const data = await response.json();
            setServices(data.services || []);
        } catch (error) {
            setServices([]);
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
                    <CardTitle>
                        Systemstatus
                        {version && (
                            <span className="ml-2 text-sm font-normal text-muted-foreground">
                                v{version}
                            </span>
                        )}
                    </CardTitle>
                    <CardDescription>
                        {lastChecked ? `Zuletzt geprüft: ${lastChecked.toLocaleTimeString()}` : 'Prüfe...'}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    {services.length === 0 && (
                        <div className="flex items-center justify-between p-4 border rounded-md">
                            <div className="flex items-center gap-4">
                                <div className="p-2 bg-muted rounded-full">
                                    <Activity className="w-6 h-6 text-foreground" />
                                </div>
                                <h4 className="font-medium">Dienste</h4>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-yellow-500" />
                                <span className="font-medium">Prüfung...</span>
                            </div>
                        </div>
                    )}
                    {services.map((service) => (
                        <div
                            key={service.name}
                            className="flex items-center justify-between p-4 border rounded-md"
                        >
                            <div className="flex items-center gap-4">
                                <div className="p-2 bg-muted rounded-full">
                                    <Activity className="w-6 h-6 text-foreground" />
                                </div>
                                <h4 className="font-medium">{service.name}</h4>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className={`w-3 h-3 rounded-full ${statusDotClass[service.status]}`} />
                                <span className="font-medium">{statusLabel[service.status]}</span>
                            </div>
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    );
};

export default SystemSettings;
