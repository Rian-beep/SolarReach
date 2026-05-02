import { useState } from "react";
import {
  Bot,
  Download,
  FileText,
  Mail,
  Music,
  Sparkles,
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
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import {
  API_BASE,
  useGeneratePitch,
  useSwarmJob,
  useSwarmRun,
} from "@/lib/api";
import { useCostConfirm } from "@/components/header/CostConfirmModal";
import { gbp } from "@/lib/utils";
import type { Lead } from "@/lib/types";

interface PitchTabProps {
  lead: Lead;
  clientId?: string;
}

const PITCH_COST_CENTS = 10;
const SWARM_COST_CENTS = 30;

export function PitchTab({
  lead,
  clientId = "client-greensolar-uk",
}: PitchTabProps) {
  const pitch = useGeneratePitch();
  const swarmRun = useSwarmRun();
  const { confirm } = useCostConfirm();

  const [swarmJobId, setSwarmJobId] = useState<string | null>(null);
  const swarmJob = useSwarmJob(swarmJobId);

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

  const onBuildSwarm = async () => {
    const ok = await confirm(
      SWARM_COST_CENTS,
      "Build outreach package (Opus 4.7 + Haiku 4.5 swarm)",
    );
    if (!ok) return;
    try {
      const res = await swarmRun.mutateAsync({
        objective: `Build full outreach package for lead ${lead._id}`,
        target_lead_id: lead._id,
      });
      setSwarmJobId(res.job_id);
      toast.success(`Swarm dispatched · ${res.job_id.slice(0, 12)}…`);
    } catch (err) {
      toast.error(`Swarm failed: ${(err as Error).message}`);
    }
  };

  const result = pitch.data;
  const job = swarmJob.data;
  const swarmRunning =
    swarmRun.isPending || job?.status === "queued" || job?.status === "running";
  const swarmDone = job?.status === "done";
  const swarmError = job?.status === "error";

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
        <CardContent className="space-y-1.5">
          <Button
            onClick={onGenerate}
            disabled={pitch.isPending}
            className="w-full"
          >
            {pitch.isPending
              ? "GENERATING…"
              : `[GENERATE PITCH] · ${gbp(PITCH_COST_CENTS, { cents: true })}`}
          </Button>
          <Button
            variant="magenta"
            onClick={onBuildSwarm}
            disabled={swarmRunning}
            className="w-full"
          >
            <Bot className="size-3.5" strokeWidth={1.5} />
            {swarmRunning
              ? `${(job?.status ?? "QUEUED").toUpperCase()}…`
              : `[BUILD OUTREACH PACKAGE — SWARM] · ~30s · ${gbp(SWARM_COST_CENTS, { cents: true })}`}
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

      {/* Swarm progress */}
      {swarmJobId && (swarmRunning || swarmDone || swarmError) && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-1.5">
                <Bot className="size-3.5 text-magenta" strokeWidth={1.5} />
                SWARM ARTIFACTS
              </CardTitle>
              <Badge variant={swarmError ? "amber" : "cyan"}>
                {(job?.status ?? "queued").toUpperCase()}
              </Badge>
            </div>
            <CardDescription className="font-mono text-[10px]">
              {swarmJobId}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {swarmRunning && (
              <div className="grid grid-cols-3 gap-1.5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="aspect-video" />
                ))}
              </div>
            )}

            {swarmError && job?.error && (
              <p className="text-xs text-amber whitespace-pre-line">
                {job.error}
              </p>
            )}

            {swarmDone && job?.artifacts && (
              <>
                <div className="flex gap-2">
                  {job.artifacts.pptx_url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      asChild
                      className="flex-1"
                    >
                      <a
                        href={`${API_BASE}${job.artifacts.pptx_url}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Download className="size-3.5" strokeWidth={1.5} />
                        [DOWNLOAD PPTX]
                      </a>
                    </Button>
                  )}
                  {job.artifacts.mp3_url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      asChild
                      className="flex-1"
                    >
                      <a
                        href={`${API_BASE}${job.artifacts.mp3_url}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Music className="size-3.5" strokeWidth={1.5} />
                        [PLAY MP3]
                      </a>
                    </Button>
                  )}
                </div>
                {job.artifacts.research_bullets.length > 0 && (
                  <div className="rounded-[2px] border border-iron bg-app-elev-1 p-2">
                    <div className="font-mono text-[10px] uppercase tracking-wide text-cyan mb-1">
                      RESEARCH
                    </div>
                    <ul className="space-y-0.5 text-xs text-bone leading-relaxed">
                      {job.artifacts.research_bullets.map((b, i) => (
                        <li key={i} className="flex gap-1.5">
                          <span className="text-dim">·</span>
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
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
