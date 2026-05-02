import { useState, type FormEvent } from "react";
import { Calculator, Leaf, MapPin, Send } from "lucide-react";
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
import { Skeleton } from "@/components/ui/Skeleton";
import { useCalculator, useSubmitInbound } from "@/lib/api";
import { gbp } from "@/lib/utils";
import type { CalculatorResponse, PremisesType } from "@/lib/types";

const PREMISES_TYPES: PremisesType[] = [
  "office",
  "leisure",
  "warehouse",
  "retail",
  "education",
];

export function CalculatorMode() {
  const [address, setAddress] = useState("");
  const [annualKwh, setAnnualKwh] = useState("12000");
  const [premisesType, setPremisesType] = useState<PremisesType>("office");
  const [breakdown, setBreakdown] = useState<CalculatorResponse | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const calc = useCalculator();
  const inbound = useSubmitInbound();

  const onCalculate = async (e: FormEvent) => {
    e.preventDefault();
    if (!address.trim()) {
      toast.error("Address required");
      return;
    }
    try {
      const res = await calc.mutateAsync({
        address: address.trim(),
        annual_kwh: Number(annualKwh) || 0,
        premises_type: premisesType,
      });
      setBreakdown(res);
      toast.success("Financial breakdown computed");
    } catch (err) {
      toast.error(`Calc failed: ${(err as Error).message}`);
    }
  };

  const onSubmitLead = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !phone.trim()) {
      toast.error("All fields required");
      return;
    }
    try {
      await inbound.mutateAsync({
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        address: address.trim(),
        annual_kwh: Number(annualKwh) || undefined,
        premises_type: premisesType,
      });
      toast.success("Lead submitted — outreach queued");
      setName("");
      setEmail("");
      setPhone("");
    } catch (err) {
      toast.error(`Submit failed: ${(err as Error).message}`);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">
      <div className="font-mono text-xs uppercase tracking-wide text-dim">
        solarreach://calculator
      </div>

      {/* Inputs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <Calculator className="size-3.5 text-cyan" strokeWidth={1.5} />
            FINANCIAL CALCULATOR
          </CardTitle>
          <CardDescription>
            Enter premises details to model capex, payback, NPV, and ECO4 grant
            eligibility.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onCalculate} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-3 space-y-1">
              <Label htmlFor="calc-address">ADDRESS</Label>
              <div className="relative">
                <MapPin
                  className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-dim pointer-events-none"
                  strokeWidth={1.5}
                />
                <Input
                  id="calc-address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="1 Old Street, London EC1Y 8AF"
                  className="pl-7 font-mono"
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="calc-kwh">ANNUAL kWh</Label>
              <Input
                id="calc-kwh"
                type="number"
                value={annualKwh}
                onChange={(e) => setAnnualKwh(e.target.value)}
                className="font-mono tabular-nums"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="calc-type">PREMISES TYPE</Label>
              <select
                id="calc-type"
                value={premisesType}
                onChange={(e) => setPremisesType(e.target.value as PremisesType)}
                className="flex h-8 w-full rounded-[2px] border border-iron bg-app-elev-1 px-2 py-1 text-sm text-bone font-mono uppercase focus-visible:outline-none focus-visible:border-cyan focus-visible:ring-1 focus-visible:ring-cyan transition-colors duration-[80ms]"
              >
                {PREMISES_TYPES.map((t) => (
                  <option key={t} value={t} className="bg-app-elev-1">
                    {t.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={calc.isPending} className="w-full">
                {calc.isPending ? "COMPUTING…" : "[CALCULATE]"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Breakdown */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>BREAKDOWN</CardTitle>
            {breakdown && (
              <Badge variant={breakdown.eco4_eligible ? "emerald" : "outline"}>
                <Leaf className="size-3 mr-1" strokeWidth={1.5} />
                ECO4{" "}
                {breakdown.eco4_eligible
                  ? `${gbp(breakdown.eco4_grant_gbp)} GRANT`
                  : "NOT ELIGIBLE"}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {calc.isPending ? (
            <div className="space-y-1.5">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ) : breakdown ? (
            <table className="w-full font-mono text-xs">
              <tbody>
                <tr className="border-b border-iron">
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    capex
                  </td>
                  <td className="py-1.5 text-right text-bone tabular-nums">
                    {gbp(breakdown.capex_gbp)}
                  </td>
                </tr>
                <tr className="border-b border-iron bg-app-elev-1/40">
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    annual saving
                  </td>
                  <td className="py-1.5 text-right text-bone tabular-nums">
                    {gbp(breakdown.annual_saving_gbp)}
                  </td>
                </tr>
                <tr className="border-b border-iron">
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    payback yrs
                  </td>
                  <td className="py-1.5 text-right text-bone tabular-nums">
                    {breakdown.payback_years.toFixed(1)}
                  </td>
                </tr>
                <tr className="border-b border-iron bg-app-elev-1/40">
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    npv 25yr
                  </td>
                  <td className="py-1.5 text-right text-emerald tabular-nums">
                    {gbp(breakdown.npv_25yr_gbp)}
                  </td>
                </tr>
                <tr className="border-b border-iron">
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    panels
                  </td>
                  <td className="py-1.5 text-right text-bone tabular-nums">
                    {breakdown.panel_count}
                  </td>
                </tr>
                <tr>
                  <td className="py-1.5 text-mute uppercase tracking-wide">
                    annual kWh
                  </td>
                  <td className="py-1.5 text-right text-bone tabular-nums">
                    {breakdown.annual_kwh.toLocaleString("en-GB")}
                  </td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="font-mono text-xs text-dim">[ -- ] no breakdown yet</p>
          )}
        </CardContent>
      </Card>

      {/* Lead-capture */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <Send className="size-3.5 text-magenta" strokeWidth={1.5} />
            REQUEST PROPOSAL
          </CardTitle>
          <CardDescription>
            Submit your details — we&apos;ll route to the nearest installer
            partner.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={onSubmitLead}
            className="grid grid-cols-1 sm:grid-cols-3 gap-3"
          >
            <div className="space-y-1">
              <Label htmlFor="ld-name">NAME</Label>
              <Input
                id="ld-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Sarah Patel"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ld-email">EMAIL</Label>
              <Input
                id="ld-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="sarah@example.co.uk"
                className="font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ld-phone">PHONE</Label>
              <Input
                id="ld-phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+44 7700 900000"
                className="font-mono"
              />
            </div>
            <div className="sm:col-span-3 flex justify-end">
              <Button type="submit" disabled={inbound.isPending}>
                {inbound.isPending ? "SUBMITTING…" : "[SUBMIT LEAD]"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
