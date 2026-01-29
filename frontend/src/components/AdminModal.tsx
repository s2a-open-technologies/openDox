import { useState } from 'react';
import { Logo } from '@/components/Logo';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { GlobeLock, BookOpenCheck, Settings, Users, Shield, Server, HardDrive } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import WhisperConfig from './settings/WhisperConfig';
import { ThemeToggle } from './settings/ThemeToggle';
import LdapSettings from './settings/LdapSettings';
import SystemSettings from './settings/SystemSettings';
import CategorySettings from './settings/CategorySettings';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AdminModal = ({ isOpen, onClose }: AdminModalProps) => {
  const [activeTab, setActiveTab] = useState('settings');

  const navItems = [
    { id: 'settings', label: 'Einstellungen', icon: Settings },
    { id: 'users', label: 'Benutzer', icon: Users },
    { id: 'permissions', label: 'Berechtigungen', icon: Shield },
    { id: 'categories', label: 'Kategorien', icon: BookOpenCheck},
    { id: 'system', label: 'System', icon: Server },
    { id: 'backup', label: 'Backup', icon: HardDrive },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'settings':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Allgemeine Einstellungen</h3>
            <div className="space-y-2">
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Systemkonfiguration</h4>
                <p className="text-sm text-muted-foreground">Grundlegende Systemeinstellungen</p>
                <div className="mt-2 space-y-2">
                  <div className="flex items-center justify-between p-2 bg-muted/50 rounded-md">
                    <span className="text-sm font-medium">Theme</span>
                    <ThemeToggle />
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      case 'users':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Benutzerverwaltung</h3>
            <div className="space-y-2">
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Benutzerliste</h4>
                <p className="text-sm text-muted-foreground">Verwalten Sie Benutzerkonten</p>
              </div>
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Rollen</h4>
                <p className="text-sm text-muted-foreground">Definieren Sie Benutzerrollen</p>
              </div>
            </div>
          </div>
        );
      case 'permissions':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Berechtigungen</h3>
            <div className="space-y-2">
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Zugriffsrechte</h4>
                <p className="text-sm text-muted-foreground">Verwalten Sie Zugriffsrechte</p>
              </div>
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Funktionen</h4>
                <p className="text-sm text-muted-foreground">Funktionsberechtigungen</p>
              </div>
            </div>
          </div>
        );
      case 'ldap':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">LDAP Integration</h3>
            <LdapSettings />
          </div>
        )
      case 'system':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Systemverwaltung</h3>
            <SystemSettings />
            <div className="space-y-2">
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Protokolle</h4>
                <p className="text-sm text-muted-foreground">Systemprotokolle anzeigen</p>
              </div>
            </div>
          </div>
        );
      case 'backup':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Datensicherung</h3>
            <div className="space-y-2">
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Sicherungsplan</h4>
                <p className="text-sm text-muted-foreground">Planen Sie regelmäßige Sicherungen</p>
              </div>
              <div className="p-4 border rounded-md">
                <h4 className="font-medium">Wiederherstellung</h4>
                <p className="text-sm text-muted-foreground">Daten wiederherstellen</p>
              </div>
            </div>
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
      <DialogContent className="max-w-4xl h-[85vh] p-0 overflow-hidden">

        <DialogHeader className="p-4 border-b z-10 relative bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 space-y-2">
          <div className="flex justify-start">
            <Logo className="h-24 w-auto" />
          </div>
        </DialogHeader>
        <div className="flex h-[calc(100%-var(--header-height))] z-10 relative">
          <div className="w-64 border-r p-2">
            <ScrollArea className="h-full">
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const IconComponent = item.icon;
                  return (
                    <button
                      key={item.id}
                      className={`w-full text-left p-3 rounded-md transition-colors flex items-center gap-2 ${activeTab === item.id
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
            </ScrollArea>
          </div>
          <div className="flex-1 p-6 overflow-auto h-[60vh]">
            {renderContent()}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AdminModal;
