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

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

const DisclaimerGate = () => {
  const { acceptDisclaimer, logout } = useAuth();
  const [confirmed, setConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAccept = async () => {
    setIsSubmitting(true);
    const ok = await acceptDisclaimer();
    setIsSubmitting(false);
    if (!ok) {
      toast.error("Bestätigung fehlgeschlagen – bitte erneut versuchen");
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
          <AlertTitle>Kein Medizinprodukt</AlertTitle>
          <AlertDescription className="text-sm leading-relaxed space-y-2">
            <p>
              openDox ist kein zugelassenes Medizinprodukt gemäß Medizinproduktegesetz (MPG)
              oder vergleichbaren Regularien (z. B. EU-MDR, FDA). Es dient ausschließlich der
              Unterstützung bei der Dokumentation.
            </p>
            <p>
              Alle maschinell erstellten Transkriptionen und Zusammenfassungen müssen von
              qualifiziertem Fachpersonal überprüft werden, bevor sie verwendet oder in eine
              Patientenakte übernommen werden. openDox ersetzt keine ärztliche Diagnose,
              Beratung oder Therapieempfehlung.
            </p>
            <p>
              Wer diese Anwendung betreibt, trägt die Verantwortung dafür, dass der Einsatz mit
              den in der eigenen Jurisdiktion geltenden Vorschriften vereinbar ist. Details siehe{" "}
              <code>DISCLAIMER.md</code> im Projekt-Repository.
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
            Ich habe den Hinweis gelesen und verstanden und bestätige, dass ich für die
            regelkonforme Nutzung dieser Anwendung verantwortlich bin.
          </label>
        </div>

        <div className="flex items-center justify-between gap-3">
          <Button variant="ghost" onClick={logout}>
            Abmelden
          </Button>
          <Button onClick={handleAccept} disabled={!confirmed || isSubmitting}>
            {isSubmitting ? "Bestätige..." : "Bestätigen"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DisclaimerGate;
