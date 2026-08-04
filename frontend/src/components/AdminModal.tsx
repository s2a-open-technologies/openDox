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

import { useState } from 'react';
import { Logo } from '@/components/Logo';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  GlobeLock, BookOpenCheck, Settings, Users, Server, HardDrive, Mic, Brain, Download
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import WhisperConfig from './settings/WhisperConfig';
import LlmConfig from './settings/LlmConfig';
import OidcSettings from './settings/OidcSettings';
import { ThemeToggle } from './settings/ThemeToggle';
import LdapSettings from './settings/LdapSettings';
import UserSettings from './settings/UserSettings';
import SystemSettings from './settings/SystemSettings';
import CategorySettings from './settings/CategorySettings';
import BackupSettings from './settings/BackupSettings';
import { AudioConfig } from './settings/AudioConfig';
import { FailedTranscriptions } from './settings/FailedTranscriptions';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AdminModal = ({ isOpen, onClose }: AdminModalProps) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [activeTab, setActiveTab] = useState(isAdmin ? 'services' : 'categories');

  // Moderatoren sehen nur Kategorien + System-Status; Admins sehen alles.
  const navItems = [
    ...(isAdmin ? [
      { id: 'services', label: 'Dienste', icon: Server },
      { id: 'audio', label: 'Audio', icon: Download },
      { id: 'users', label: 'Benutzer', icon: Users },
      { id: 'auth', label: 'Authentifizierung', icon: GlobeLock },
      { id: 'backup', label: 'Backup', icon: HardDrive },
    ] : []),
    { id: 'categories', label: 'Kategorien', icon: BookOpenCheck },
    { id: 'system', label: 'System', icon: Settings },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'services':
        return (
          <div className="space-y-6">
            <div className="flex items-center gap-2 mb-2">
              <Server className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-medium">API-Dienste konfigurieren</h3>
            </div>
            
            <Tabs defaultValue="whisper" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="whisper" className="flex items-center gap-2">
                  <Mic className="w-4 h-4" />
                  <span>Whisper / ASR</span>
                </TabsTrigger>
                <TabsTrigger value="llm" className="flex items-center gap-2">
                  <Brain className="w-4 h-4" />
                  <span>LLM</span>
                </TabsTrigger>
              </TabsList>

              <TabsContent value="whisper">
                <WhisperConfig />
              </TabsContent>

              <TabsContent value="llm">
                <LlmConfig />
              </TabsContent>
            </Tabs>
          </div>
        );
      case 'audio':
        return (
          <div className="space-y-6">
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Audio-Download-Einstellungen</h3>
              <AudioConfig />
            </div>
            <FailedTranscriptions />
          </div>
        );
      case 'users':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Benutzerverwaltung</h3>
            <UserSettings />
          </div>
        );
      case 'auth':
        return (
          <div className="space-y-6">
            <div className="flex items-center gap-2 mb-2">
              <GlobeLock className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-medium">Authentifizierung</h3>
            </div>
            <Tabs defaultValue="ldap" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="ldap">LDAP</TabsTrigger>
                <TabsTrigger value="oidc">OIDC / SSO</TabsTrigger>
              </TabsList>
              <TabsContent value="ldap">
                <LdapSettings />
              </TabsContent>
              <TabsContent value="oidc">
                <OidcSettings />
              </TabsContent>
            </Tabs>
          </div>
        );
      case 'system':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Systemverwaltung</h3>
            <SystemSettings />
          </div>
        );
      case 'backup':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Datensicherung</h3>
            <BackupSettings />
          </div>
        );
      case 'categories':
        return (
          <div className="space-y-4">
            <CategorySettings />
          </div>
        );
      default:
        return <div>Wählen Sie eine Option aus der Navigation</div>;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[85dvh] p-0 overflow-hidden flex flex-col">

        <DialogHeader className="p-4 border-b z-10 relative bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 space-y-2">
          <div className="flex justify-start">
            <Logo className="h-24 w-auto" />
          </div>
        </DialogHeader>
        <div className="flex flex-col md:flex-row flex-1 min-h-0 z-10 relative">
          <div className="w-full md:w-64 border-b md:border-b-0 md:border-r p-2 overflow-x-auto md:overflow-x-visible md:overflow-y-auto">
            <nav className="flex md:flex-col gap-1">
              {navItems.map((item) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={item.id}
                    className={`flex-shrink-0 md:w-full text-left p-3 rounded-md transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === item.id
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                      }`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    <IconComponent className="w-4 h-4" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>
          <div className="flex-1 p-4 md:p-6 overflow-auto min-h-0">
            {renderContent()}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AdminModal;
