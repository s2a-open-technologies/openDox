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

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";
import { User, LogOut, Settings, Sun, Moon } from "lucide-react";
import { useState } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import AdminModal from "./AdminModal";

const UserDropdown = () => {
    const { user, logout } = useAuth();
    const { theme, toggleTheme } = useTheme();
    const [showAdmin, setShowAdmin] = useState(false);

    return (
        <>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="relative h-10 w-full justify-start gap-2 pl-2">
                        <Avatar className="h-8 w-8">
                            <AvatarImage src="/avatars/01.png" alt={user?.name} />
                            <AvatarFallback>{user?.name?.charAt(0).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div className="flex flex-col items-start text-sm">
                            <span className="font-medium">{user?.name}</span>
                            <span className="text-xs text-muted-foreground">Online</span>
                        </div>
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56" align="end" forceMount>
                    <DropdownMenuLabel className="font-normal">
                        <div className="flex flex-col space-y-1">
                            <p className="text-sm font-medium leading-none">{user?.name}</p>
                            <p className="text-xs leading-none text-muted-foreground">
                                {user?.role === 'admin' ? 'Administrator' : user?.role === 'moderator' ? 'Moderator' : 'Benutzer'}
                            </p>
                        </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={toggleTheme}>
                        {theme === 'dark' ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
                        <span>{theme === 'dark' ? 'Helles Design' : 'Dunkles Design'}</span>
                    </DropdownMenuItem>
                    {user?.role !== 'user' && (
                        <DropdownMenuItem onClick={() => {
                            setTimeout(() => setShowAdmin(true), 100);
                        }}>
                            <Settings className="mr-2 h-4 w-4" />
                            <span>Administration</span>
                        </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={logout}>
                        <LogOut className="mr-2 h-4 w-4" />
                        <span>Abmelden</span>
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>

            <AdminModal isOpen={showAdmin} onClose={() => setShowAdmin(false)} />
        </>
    );
};

export default UserDropdown;
