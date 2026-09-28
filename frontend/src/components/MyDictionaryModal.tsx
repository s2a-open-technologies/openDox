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

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import PersonalDictionary from './settings/PersonalDictionary';

interface MyDictionaryModalProps {
    isOpen: boolean;
    onClose: () => void;
}

const MyDictionaryModal = ({ isOpen, onClose }: MyDictionaryModalProps) => (
    <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-2xl max-h-[85dvh] overflow-y-auto">
            <DialogHeader>
                <DialogTitle>Mein Wörterbuch</DialogTitle>
                <DialogDescription>
                    Ihr persönliches Korrektur-Wörterbuch, das bei jeder Ihrer Aufnahmen
                    angewendet wird, unabhängig vom gewählten Profil.
                </DialogDescription>
            </DialogHeader>
            <PersonalDictionary />
        </DialogContent>
    </Dialog>
);

export default MyDictionaryModal;
