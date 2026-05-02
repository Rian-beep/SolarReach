import { Download, FileText, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { useGeneratePitch, API_BASE } from "@/lib/api";
import { useCostConfirm } from "@/components/header/CostConfirmModal";
import { gbp } from "@/lib/utils";
import type { Lead } from "@/lib/types";

interface PitchTabProps {
  lead: Lead;
  clientId?: string;
}

const PITCH_COST_CENTS = 10;

export function PitchTab({
  lead,
  clientId = "client-greensolar-uk",
}: PitchTabProps) {
  const pitch = useGeneratePitch();
  const { confirm } = useCostConfirm();

  const onGenerate = async () => {
    const ok = await confirm(
      PITCH_COST_CENTS,
      "Generate pitch deck (Sonnet 4.6 + PPTX)",
    );
    if (!ok) return;
    try {
      await pitch.mutateAsync({ leadId: lead._id, clientId });
      toast.success("Pitch deck generated");
    } catch (err) {
      toast.error(`Pitch failed: ${(err as Error).message}`);
    }
  };

  const result = pitch.data;

  return (
    <div className="space-y-3">
      {/* Generate */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5">
            <Sparkles className="size-3.5 text-cyan" strokeWidth={1.5} />
            GENERATE PITCH
          </CardTitle>
          <CardDescription>
            Sonnet 4.6 with prompt cache &rarr; 11-slide PPTX &rarr; libreoffice
            &rarr; PDF.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            onClick={onGenerate}
            disabled={pitch.isPending}
            className="w-full"
          >
            {pitch.isPending
              ? "GENERATING…"
              : `[GENERATE PITCH] · ${gbp(PITCH_COST_CENTS, { cents: true })}`}
          </Button>
        </CardContent>
      </Card>

      {/* Loading */}
      {pitch.isPending && (
        <Card>
          <CardHeader>
            <CardTitle>RENDERING DECK</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-1.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="aspect-video" />
            ))}
          </CardContent>
        </Card>
      )}

      {result && (
        <>
          {/* Slide thumbnails */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>DECK PREVIEW</CardTitle>
                <Badge variant="cyan">SONNET 4.6</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-1.5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="aspect-video rounded-[2px] border border-iron bg-app-elev-1 p-1.5 flex flex-col justify-between hover:border-cyan transition-colors duration-[80ms]"
                  >
                    <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-wide text-grid">
                      <span>SLIDE</span>
                      <span>{String(i + 1).padStart(2, "0")}</span>
                    </div>
                    <div className="space-y-0.5">
                      <div className="h-0.5 w-2/3 bg-iron-bright" />
                      <div className="h-0.5 w-full bg-iron" />
                      <div className="h-0.5 w-3/4 bg-iron" />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Artifacts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <FileText className="size-3.5 text-mute" strokeWidth={1.5} />
                ARTIFACTS
              </CardTitle>
            </CardHeader>
            <CardContent className="flex gap-2">
              {result.pptx_url && (
                <Button variant="ghost" size="sm" asChild className="flex-1">
                  <a
                    href={`${API_BASE}${result.pptx_url}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Download className="size-3.5" strokeWidth={1.5} />
                    [DOWNLOAD PPTX]
                  </a>
                </Button>
              )}
              {result.pdf_url && (
                <Button variant="ghost" size="sm" asChild className="flex-1">
                  <a
                    href={`${API_BASE}${result.pdf_url}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Download className="size-3.5" strokeWidth={1.5} />
                    [DOWNLOAD PDF]
                  </a>
                </Button>
              )}
            </CardContent>
          </Card>

          {/* A/B Email previews */}
          {result.emails && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-1.5">
                    <Mail className="size-3.5 text-cyan" strokeWidth={1.5} />
                    A/B EMAIL VARIANTS
                  </CardTitle>
                  <span className="flex items-center gap-1 font-mono text-xs uppercase tracking-wide text-magenta">
                    <span className="size-1.5 rounded-full bg-magenta animate-live-dot" />
                    LIVE
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {(["a", "b"] as const).map((variant) => {
                  const email = result.emails?.[variant];
                  if (!email) return null;
                  return (
                    <div
                      key={variant}
                      className="rounded-[2px] border border-iron bg-app-elev-1 p-2"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs uppercase tracking-wide text-cyan">
                          VARIANT {variant.toUpperCase()}
                        </span>
                        <span className="font-mono text-xs text-dim tabular-nums">
                          {email.length} chars
                        </span>
                      </div>
                      <p className="text-xs text-bone whitespace-pre-line line-clamp-6 leading-relaxed">
                        {email}
                      </p>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
