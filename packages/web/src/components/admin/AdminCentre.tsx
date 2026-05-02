import { useState, type FormEvent } from "react";
import { Settings2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Badge } from "@/components/ui/Badge";
import { useClient, useSaveAdmin } from "@/lib/api";

interface AdminCentreProps {
  clientSlug?: string;
}

export function AdminCentre({
  clientSlug = "client-greensolar-uk",
}: AdminCentreProps) {
  // All hooks before any conditional return
  const client = useClient(clientSlug);
  const save = useSaveAdmin();

  const [primary, setPrimary] = useState("#1FB6FF");
  const [panelUnit, setPanelUnit] = useState("850");
  const [installPerKw, setInstallPerKw] = useState("180");
  const [budget, setBudget] = useState("1");
  const [hydrated, setHydrated] = useState(false);

  // Hydrate when client data lands
  if (client.data && !hydrated) {
    setHydrated(true);
    setPrimary(client.data.branding?.primary ?? "#1FB6FF");
    setPanelUnit(String(client.data.pricing?.panel_unit_gbp ?? 850));
    setInstallPerKw(String(client.data.pricing?.install_per_kw_gbp ?? 180));
    setBudget(String(client.data.session_budget_gbp ?? 1));
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await save.mutateAsync({
        slug: clientSlug,
        payload: {
          branding: { primary },
          pricing: {
            panel_unit_gbp: Number(panelUnit) || 0,
            install_per_kw_gbp: Number(installPerKw) || 0,
          },
          session_budget_gbp: Number(budget) || 0,
        },
      });
      toast.success("Client config saved");
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 space-y-4">
      <div className="font-mono text-xs uppercase tracking-wide text-dim">
        solarreach://admin
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-1.5">
              <Settings2 className="size-3.5 text-cyan" strokeWidth={1.5} />
              CLIENT CONFIG
            </CardTitle>
            <Badge variant="mono">{clientSlug}</Badge>
          </div>
          <CardDescription>
            Branding, pricing, and per-session AI budget for this tenant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="adm-slug">CLIENT SLUG</Label>
                <Input
                  id="adm-slug"
                  value={clientSlug}
                  readOnly
                  className="font-mono text-dim cursor-not-allowed bg-app-void"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="adm-primary">BRAND PRIMARY</Label>
                <div className="flex gap-2">
                  <input
                    id="adm-primary-color"
                    type="color"
                    value={primary}
                    onChange={(e) => setPrimary(e.target.value)}
                    className="h-8 w-10 rounded-[2px] border border-iron bg-app-elev-1 p-0.5 cursor-pointer"
                  />
                  <Input
                    id="adm-primary"
                    value={primary}
                    onChange={(e) => setPrimary(e.target.value)}
                    className="font-mono"
                    placeholder="#1FB6FF"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="adm-panel">PANEL UNIT GBP</Label>
                <Input
                  id="adm-panel"
                  type="number"
                  step="10"
                  value={panelUnit}
                  onChange={(e) => setPanelUnit(e.target.value)}
                  className="font-mono tabular-nums"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="adm-install">INSTALL £/kW</Label>
                <Input
                  id="adm-install"
                  type="number"
                  step="5"
                  value={installPerKw}
                  onChange={(e) => setInstallPerKw(e.target.value)}
                  className="font-mono tabular-nums"
                />
              </div>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Label htmlFor="adm-budget">SESSION BUDGET (GBP)</Label>
                <span className="font-mono text-xs text-cyan tabular-nums">
                  £{Number(budget).toFixed(2)}
                </span>
              </div>
              <input
                id="adm-budget"
                type="range"
                min="0.10"
                max="5.00"
                step="0.10"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full accent-cyan"
              />
              <div className="flex justify-between font-mono text-xs text-grid tabular-nums">
                <span>£0.10</span>
                <span>£5.00</span>
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={save.isPending}>
                {save.isPending ? "SAVING…" : "[SAVE CONFIG]"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {client.isError && (
        <p className="font-mono text-xs text-red">
          Failed to load client: {client.error.message}
        </p>
      )}
    </div>
  );
}
