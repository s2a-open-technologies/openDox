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
import { User, LogOut, Settings } from "lucide-react";
import { useState } from "react";
import AdminModal from "./AdminModal";

const UserDropdown = () => {
    const { user, logout } = useAuth();
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
                                {user?.is_superuser ? 'Administrator' : 'Benutzer'}
                            </p>
                        </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {user?.is_superuser && (
                        <DropdownMenuItem onClick={() => {
                            // Delay opening modal to allow dropdown to close properly and avoid focus lock
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
