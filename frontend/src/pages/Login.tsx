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

import { useTranslation } from "react-i18next";
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Mic, KeyRound } from "lucide-react";
import { toast } from "sonner";

const Login = () => {
  const { t } = useTranslation("login");
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [oidcEnabled, setOidcEnabled] = useState(false);
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // OIDC callback: tokens arrive as query params after the provider redirect.
  useEffect(() => {
    const access = searchParams.get("access_token");
    const refresh = searchParams.get("refresh_token");
    if (access) {
      localStorage.setItem("access_token", access);
      if (refresh) localStorage.setItem("refresh_token", refresh);
      // Clean the URL so tokens don't linger in the address bar / history.
      navigate("/dashboard", { replace: true });
    }
  }, [searchParams, navigate]);

  // Show SSO button only if the admin has enabled OIDC.
  useEffect(() => {
    fetch("/api/v1/auth/oidc/status")
      .then((res) => res.json())
      .then((data) => setOidcEnabled(data.enabled === true))
      .catch(() => setOidcEnabled(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const success = await login(user, password);
      if (success) {
        toast.success(t("success"));
      } else {
        toast.error(t("failed"));
      }
    } catch (error) {
      toast.error(t("failed"));
    }
  };

  const handleOidcLogin = () => {
    // Full-page redirect to the backend OIDC login endpoint; the provider
    // redirect chain ends with the browser returning here with tokens.
    window.location.href = "/api/v1/auth/oidc/login";
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto w-12 h-12 bg-primary rounded-full flex items-center justify-center">
            <Mic className="w-6 h-6 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">{t("welcome")}</CardTitle>
          <CardDescription>
            {t("subtitle")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Input
                type="text"
                placeholder={t("username")}
                value={user}
                onChange={(e) => setUser(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Input
                type="password"
                placeholder={t("password")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full">
              {t("submit")}
            </Button>

            {oidcEnabled && (
              <>
                <div className="relative my-2">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-card px-2 text-muted-foreground">{t("or")}</span>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full gap-2"
                  onClick={handleOidcLogin}
                >
                  <KeyRound className="w-4 h-4" />
                  {t("sso")}
                </Button>
              </>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
