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

import { Trans, useTranslation } from "react-i18next";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

const DisclaimerGate = () => {
  const { t } = useTranslation(["disclaimer", "common"]);
  const { acceptDisclaimer, logout } = useAuth();
  const [confirmed, setConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAccept = async () => {
    setIsSubmitting(true);
    const ok = await acceptDisclaimer();
    setIsSubmitting(false);
    if (!ok) {
      toast.error(t("gate.failed"));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background p-4 overflow-y-auto">
      <div className="w-full max-w-2xl space-y-6 py-8">
        <div className="flex justify-center">
          <Logo className="h-16 w-auto" />
        </div>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{t("title")}</AlertTitle>
          <AlertDescription className="text-sm leading-relaxed space-y-2">
            <p>{t("gate.p1")}</p>
            <p>{t("gate.p2")}</p>
            <p>
              <Trans t={t} i18nKey="gate.p3" components={{ code: <code /> }} />
            </p>
          </AlertDescription>
        </Alert>

        <div className="flex items-start gap-3 rounded-md border p-4">
          <Checkbox
            id="disclaimer-confirm"
            checked={confirmed}
            onCheckedChange={(checked) => setConfirmed(checked === true)}
            className="mt-0.5"
          />
          <label htmlFor="disclaimer-confirm" className="text-sm text-muted-foreground cursor-pointer">
            {t("gate.confirm")}
          </label>
        </div>

        <div className="flex items-center justify-between gap-3">
          <Button variant="ghost" onClick={logout}>
            {t("common:logout")}
          </Button>
          <Button onClick={handleAccept} disabled={!confirmed || isSubmitting}>
            {isSubmitting ? t("gate.submitting") : t("gate.submit")}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DisclaimerGate;
