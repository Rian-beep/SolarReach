import { useState, type FormEvent } from "react";
import {
  BookOpen,
  Boxes,
  Package,
  Settings2,
} from "lucide-react";
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
import type { PricingTier } from "@/lib/types";

interface AdminCentreProps {
  clientSlug?: string;
}

const DEFAULT_TIERS: PricingTier[] = [
  {
    id: "starter",
    name: "Starter",
    price_gbp: 0,
    features: ["Basic calculator", "Single-site quotes", "Email support"],
  },
  {
    id: "pro",
    name: "Pro",
    price_gbp: 199,
    features: ["Multi-site portfolio", "Pitch deck generation", "Priority support"],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price_gbp: 999,
    features: ["Custom branding", "API access", "Dedicated CSM"],
  },
];

export function AdminCentre({
  clientSlug = "client-greensolar-uk",
}: AdminCentreProps) {
  // All hooks before any conditional return
  const client = useClient(clientSlug);
  const save = useSaveAdmin();

  // CLIENT CONFIG (existing)
  const [primary, setPrimary] = useState("#1FB6FF");
  const [panelUnit, setPanelUnit] = useState("850");
  const [installPerKw, setInstallPerKw] = useState("180");
  const [budget, setBudget] = useState("1");

  // PRODUCT PAGE
  const [productDescription, setProductDescription] = useState("");
  const [productFeatures, setProductFeatures] = useState<[string, string, string]>([
    "",
    "",
    "",
  ]);
  const [warrantyTerms, setWarrantyTerms] = useState("");

  // PRICING TIERS
  const [tiers, setTiers] = useState<PricingTier[]>(DEFAULT_TIERS);

  // OUTREACH AGENT CONTEXT
  const [expertiseNotes, setExpertiseNotes] = useState("");

  const [hydrated, setHydrated] = useState(false);

  // Hydrate when client data lands
  if (client.data && !hydrated) {
    setHydrated(true);
    setPrimary(client.data.branding?.primary ?? "#1FB6FF");
    setPanelUnit(String(client.data.pricing?.panel_unit_gbp ?? 850));
    setInstallPerKw(String(client.data.pricing?.install_per_kw_gbp ?? 180));
    setBudget(String(client.data.session_budget_gbp ?? 1));

    setProductDescription(client.data.product_description ?? "");
    const feats = client.data.product_features ?? [];
    setProductFeatures([
      feats[0] ?? "",
      feats[1] ?? "",
      feats[2] ?? "",
    ]);
    setWarrantyTerms(client.data.warranty_terms ?? "");

    if (client.data.pricing_tiers && client.data.pricing_tiers.length === 3) {
      setTiers(client.data.pricing_tiers);
    }

    setExpertiseNotes(client.data.expertise_notes ?? "");
  }

  const updateTierPrice = (idx: number, value: string) => {
    setTiers((prev) =>
      prev.map((t, i) => (i === idx ? { ...t, price_gbp: Number(value) || 0 } : t)),
    );
  };
  const updateTierFeature = (
    tierIdx: number,
    featIdx: number,
    value: string,
  ) => {
    setTiers((prev) =>
      prev.map((t, i) =>
        i === tierIdx
          ? {
              ...t,
              features: t.features.map((f, fi) => (fi === featIdx ? value : f)),
            }
          : t,
      ),
    );
  };

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
          product_description: productDescription.trim(),
          product_features: productFeatures.map((f) => f.trim()).filter(Boolean),
          warranty_terms: warrantyTerms.trim(),
          pricing_tiers: tiers,
          expertise_notes: expertiseNotes.trim(),
        },
      });
      toast.success("Client config saved · pitch + outreach will pick up changes on next run");
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 space-y-4">
      <div className="font-mono text-xs uppercase tracking-wide text-dim">
        solarreach://admin
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        {/* ── CLIENT CONFIG (existing) ──────────────────────────────────── */}
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
            <div className="space-y-4">
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
            </div>
          </CardContent>
        </Card>

        {/* ── PRODUCT PAGE ─────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Package className="size-3.5 text-amber" strokeWidth={1.5} />
              PRODUCT PAGE
            </CardTitle>
            <CardDescription>
              Description + 3 key features + warranty. Spliced into pitch decks
              and outreach emails.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="adm-product-desc">DESCRIPTION</Label>
              <textarea
                id="adm-product-desc"
                value={productDescription}
                onChange={(e) => setProductDescription(e.target.value)}
                rows={3}
                placeholder="Tier-1 monocrystalline panels · 25-year performance guarantee · MCS-certified install."
                className="w-full rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1.5 font-mono text-xs text-bone placeholder:text-grid focus:border-cyan focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-1">
                  <Label htmlFor={`adm-feat-${i}`}>
                    FEATURE {i + 1}
                  </Label>
                  <Input
                    id={`adm-feat-${i}`}
                    value={productFeatures[i]}
                    onChange={(e) => {
                      const v = e.target.value;
                      setProductFeatures((prev) => {
                        const next: [string, string, string] = [...prev] as [
                          string,
                          string,
                          string,
                        ];
                        next[i] = v;
                        return next;
                      });
                    }}
                    placeholder={
                      i === 0
                        ? "MCS-certified"
                        : i === 1
                          ? "0% finance available"
                          : "Battery-ready inverter"
                    }
                    className="font-mono"
                  />
                </div>
              ))}
            </div>

            <div className="space-y-1">
              <Label htmlFor="adm-warranty">WARRANTY TERMS</Label>
              <textarea
                id="adm-warranty"
                value={warrantyTerms}
                onChange={(e) => setWarrantyTerms(e.target.value)}
                rows={2}
                placeholder="25 years on panels · 10 years on inverter · 5 years on workmanship."
                className="w-full rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1.5 font-mono text-xs text-bone placeholder:text-grid focus:border-cyan focus:outline-none"
              />
            </div>
          </CardContent>
        </Card>

        {/* ── PRICING TIERS ────────────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Boxes className="size-3.5 text-magenta" strokeWidth={1.5} />
              PRICING TIERS
            </CardTitle>
            <CardDescription>
              Starter / Pro / Enterprise — surfaced in pitch decks and the
              calculator response.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {tiers.map((tier, tIdx) => (
                <Card key={tier.id} className="bg-app-elev-1">
                  <CardHeader className="pb-1">
                    <div className="flex items-center justify-between">
                      <CardTitle>{tier.name.toUpperCase()}</CardTitle>
                      <Badge variant="mono">{tier.id}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="space-y-1">
                      <Label htmlFor={`adm-tier-${tIdx}-price`}>
                        PRICE (£/MO)
                      </Label>
                      <Input
                        id={`adm-tier-${tIdx}-price`}
                        type="number"
                        step="1"
                        value={tier.price_gbp}
                        onChange={(e) => updateTierPrice(tIdx, e.target.value)}
                        className="font-mono tabular-nums"
                      />
                    </div>
                    <div className="space-y-1">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-grid">
                        FEATURES
                      </span>
                      {tier.features.map((feat, fIdx) => (
                        <Input
                          key={fIdx}
                          value={feat}
                          onChange={(e) =>
                            updateTierFeature(tIdx, fIdx, e.target.value)
                          }
                          className="font-mono text-[11px]"
                        />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ── OUTREACH AGENT CONTEXT ───────────────────────────────────── */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <BookOpen className="size-3.5 text-cyan" strokeWidth={1.5} />
              OUTREACH AGENT CONTEXT
            </CardTitle>
            <CardDescription>
              Subject-expertise notes spliced into the outreach Haiku agent's
              system prompt as <span className="font-mono text-bone">{"{client.expertise_notes}"}</span>.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <Label htmlFor="adm-expertise">SUBJECT EXPERTISE NOTES</Label>
              <textarea
                id="adm-expertise"
                value={expertiseNotes}
                onChange={(e) => setExpertiseNotes(e.target.value)}
                rows={6}
                placeholder="20-year track record on warehouse roof PV in the south-east. Known for ROCC-compliant installs on listed buildings. Banking-sector references on request."
                className="w-full rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1.5 font-mono text-xs text-bone placeholder:text-grid focus:border-cyan focus:outline-none"
              />
              <div className="font-mono text-[10px] text-grid">
                Tip: domain wins, marquee references, regulatory edge. Keep it
                tight — the agent reads this on every email.
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "SAVING…" : "[SAVE CONFIG]"}
          </Button>
        </div>
      </form>

      {client.isError && (
        <p className="font-mono text-xs text-red">
          Failed to load client: {client.error.message}
        </p>
      )}
    </div>
  );
}
