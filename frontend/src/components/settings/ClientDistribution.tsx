/*
  openDox - Medical transcription platform
  Copyright (C) 2026  Christopher Abanilla <christopher.abanilla@gmx.de>
  SPDX-FileCopyrightText: 2026 Christopher Abanilla <christopher.abanilla@gmx.de>
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
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, Copy } from "lucide-react";
import { toast } from "sonner";

interface Distribution {
  server_url: string;
  download_base_url: string;
  files: Record<string, string>;
}

// Zielpfad der MSI-Installation (opendox-client: build/windows/installer/DEPLOYMENT.md).
const INSTALL_DIR = "%ProgramFiles%\\openDox\\openDox";

const DOWNLOADS: { key: string; labelKey: string }[] = [
  { key: "windows_msi", labelKey: "distribution.windowsMsi" },
  { key: "windows_exe", labelKey: "distribution.windowsExe" },
  { key: "macos_zip", labelKey: "distribution.macos" },
];

export function ClientDistribution() {
  const { t } = useTranslation(["clients", "common"]);
  const { authFetch } = useAuth();
  const [dist, setDist] = useState<Distribution | null>(null);

  useEffect(() => {
    authFetch("/api/v1/settings/client-distribution/")
      .then(res => (res.ok ? res.json() : null))
      .then((data: Distribution | null) => setDist(data))
      .catch(console.error);
  }, []);

  if (!dist) {
    return null;
  }

  const msi = dist.files.windows_msi;
  const commands = [
    {
      label: t("distribution.intune"),
      text: `msiexec /i ${msi} /qn && copy /Y settings.json "${INSTALL_DIR}\\settings.json"`,
    },
    {
      label: t("distribution.sccm"),
      text: `Start-Process msiexec.exe -ArgumentList '/i ${msi} /qn' -Wait\nCopy-Item .\\settings.json "$env:ProgramFiles\\openDox\\openDox\\settings.json" -Force`,
    },
  ];

  // Die settings.json enthält nur die Server-Adresse; alles andere holt sich der
  // Client über /api/v1/settings/client-config/.
  const downloadSettings = () => {
    const json = JSON.stringify({ server_url: dist.server_url }, null, 2) + "\n";
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "settings.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(t("distribution.copied"));
    } catch {
      toast.error(t("distribution.copyFailed"));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("distribution.title")}</CardTitle>
        <CardDescription>{t("distribution.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <h4 className="text-sm font-medium">{t("distribution.step1")}</h4>
          <div className="flex flex-wrap gap-2">
            {DOWNLOADS.filter(d => dist.files[d.key]).map(d => (
              <Button key={d.key} variant="outline" asChild>
                <a href={`${dist.download_base_url}/${dist.files[d.key]}`} target="_blank" rel="noopener noreferrer">
                  <Download className="w-4 h-4 mr-2" />
                  {t(d.labelKey)}
                </a>
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <h4 className="text-sm font-medium">{t("distribution.step2")}</h4>
          <p className="text-sm text-muted-foreground">
            {t("distribution.serverUrl")} <code className="px-1 rounded bg-muted">{dist.server_url}</code>
          </p>
          <Button variant="outline" onClick={downloadSettings}>
            <Download className="w-4 h-4 mr-2" />
            {t("distribution.settingsJson")}
          </Button>
          <p className="text-xs text-muted-foreground">{t("distribution.serverUrlHint")}</p>
        </div>
        <div className="space-y-2">
          <h4 className="text-sm font-medium">{t("distribution.step3")}</h4>
          {commands.map(c => (
            <div key={c.label} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-sm">{c.label}</span>
                <Button variant="ghost" size="sm" onClick={() => copy(c.text)} aria-label={t("distribution.copy")}>
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              <pre className="text-xs p-2 rounded bg-muted whitespace-pre-wrap break-all">{c.text}</pre>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">{t("distribution.singleHint", { dir: INSTALL_DIR })}</p>
        </div>
      </CardContent>
    </Card>
  );
}
