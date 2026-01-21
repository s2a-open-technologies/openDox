import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Mic } from "lucide-react";
import { toast } from "sonner";

const Login = () => {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const success = await login(user, password);
      if (success) {
        toast.success("Erfolgreich angemeldet");
      } else {
        toast.error("Anmeldung fehlgeschlagen");
      }
    } catch (error) {
      toast.error("Anmeldung fehlgeschlagen");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto w-12 h-12 bg-primary rounded-full flex items-center justify-center">
            <Mic className="w-6 h-6 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Willkommen zurück</CardTitle>
          <CardDescription>
            Melden Sie sich an, um Ihre Aufnahmen zu verwalten
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Input
                type="text"
                placeholder="Username"
                value={user}
                onChange={(e) => setUser(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Input
                type="password"
                placeholder="Passwort"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full">
              Anmelden
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
