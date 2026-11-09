/*
  openDox - Medical transcription platform
  Copyright (C) 2026  S2A Open Technologies gGmbH
  SPDX-FileCopyrightText: 2026 S2A Open Technologies gGmbH
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

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, ExternalLink } from "lucide-react";

interface Manual {
  key: string;
  file: string;
  url: string;
}

interface ManualsResponse {
  version: string;
  release_url: string;
  manuals: Manual[];
}

// Die Links zeigen auf die PDFs, die release.yml an jedes GitHub-Release hängt;
// der Browser lädt sie direkt dort (oder vom Mirror aus MANUALS_DOWNLOAD_BASE_URL).
export function ManualDownloads() {
  const { t } = useTranslation("manuals");
  const { authFetch } = useAuth();
  const [data, setData] = useState<ManualsResponse | null>(null);

  useEffect(() => {
    authFetch("/api/v1/settings/manuals/")
      .then(res => (res.ok ? res.json() : null))
      .then((body: ManualsResponse | null) => setData(body))
      .catch(console.error);
  }, []);

  if (!data) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("heading")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {data.manuals.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("unavailable")}</p>
        ) : (
          <div className="flex flex-col gap-2 max-w-sm">
            {data.manuals.map(m => (
              <Button key={m.key} variant="outline" className="w-full justify-start" asChild>
                <a href={m.url} target="_blank" rel="noopener noreferrer" title={m.file}>
                  <Download className="w-4 h-4 mr-2" />
                  {t(m.key)}
                </a>
              </Button>
            ))}
          </div>
        )}
        {data.release_url && (
          <Button variant="link" className="px-0" asChild>
            <a href={data.release_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="w-4 h-4 mr-2" />
              {t("releasePage")}
            </a>
          </Button>
        )}
        <p className="text-xs text-muted-foreground">{t("hint")}</p>
      </CardContent>
    </Card>
  );
}
