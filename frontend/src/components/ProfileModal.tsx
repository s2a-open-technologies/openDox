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

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { BookMarked, BookOpenCheck, Languages, Palette } from 'lucide-react';
import { Logo } from '@/components/Logo';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuth } from '@/contexts/AuthContext';
import { SUPPORTED_LANGUAGES, isSupportedLanguage } from '@/i18n';
import CategorySettings from './settings/CategorySettings';
import PersonalDictionary from './settings/PersonalDictionary';
import { ThemeToggle } from './settings/ThemeToggle';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ProfileModal = ({ isOpen, onClose }: ProfileModalProps) => {
  const { t, i18n } = useTranslation('profile');
  const { user, updateUiLanguage } = useAuth();
  const [activeTab, setActiveTab] = useState('language');

  // Admins/moderators manage categories in the admin modal; only plain users
  // get their personal-category tab here (same rule as the old dropdown).
  const navItems = [
    { id: 'language', label: t('tabs.language'), icon: Languages },
    { id: 'dictionary', label: t('tabs.dictionary'), icon: BookMarked },
    ...(user?.role === 'user'
      ? [{ id: 'categories', label: t('tabs.categories'), icon: BookOpenCheck }]
      : []),
    { id: 'appearance', label: t('tabs.appearance'), icon: Palette },
  ];

  const handleLanguageChange = async (code: string) => {
    if (!isSupportedLanguage(code)) return;
    const ok = await updateUiLanguage(code);
    // Read the translations after the switch so the toast uses the new language.
    if (ok) toast.success(i18n.t('language.saved', { ns: 'profile' }));
    else toast.error(i18n.t('language.saveFailed', { ns: 'profile' }));
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'language':
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">{t('language.heading')}</h3>
              <p className="text-sm text-muted-foreground">{t('language.description')}</p>
            </div>
            <div className="space-y-2 max-w-xs">
              <Label htmlFor="ui-language">{t('language.label')}</Label>
              <Select
                value={isSupportedLanguage(i18n.language) ? i18n.language : undefined}
                onValueChange={handleLanguageChange}
              >
                <SelectTrigger id="ui-language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_LANGUAGES.map((l) => (
                    <SelectItem key={l.code} value={l.code}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        );
      case 'dictionary':
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">{t('dictionary.heading')}</h3>
              <p className="text-sm text-muted-foreground">{t('dictionary.description')}</p>
            </div>
            <PersonalDictionary />
          </div>
        );
      case 'categories':
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">{t('categories.heading')}</h3>
              <p className="text-sm text-muted-foreground">{t('categories.description')}</p>
            </div>
            <CategorySettings />
          </div>
        );
      case 'appearance':
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium">{t('appearance.heading')}</h3>
              <p className="text-sm text-muted-foreground">{t('appearance.description')}</p>
            </div>
            <ThemeToggle />
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl h-[85dvh] p-0 overflow-hidden flex flex-col">
        <DialogHeader className="p-4 border-b z-10 relative bg-background/95 backdrop-blur-sm supports-backdrop-filter:bg-background/60 space-y-2">
          <div className="flex justify-start">
            <Logo className="h-24 w-auto" />
          </div>
          <DialogTitle className="sr-only">{t('title')}</DialogTitle>
          <DialogDescription className="sr-only">{user?.name}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col md:flex-row flex-1 min-h-0 z-10 relative">
          <div className="w-full md:w-64 border-b md:border-b-0 md:border-r p-2 overflow-x-auto md:overflow-x-visible md:overflow-y-auto">
            <nav className="flex md:flex-col gap-1">
              {navItems.map((item) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={item.id}
                    className={`shrink-0 md:w-full text-left p-3 rounded-md transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === item.id
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
          <div className="flex-1 p-4 md:p-6 overflow-auto min-h-0">{renderContent()}</div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ProfileModal;
