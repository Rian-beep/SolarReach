import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import { useDrawerStore } from "@/stores/useDrawerStore";
import { Badge } from "@/components/ui/Badge";
import { caption } from "@/lib/utils";
import { IntelTab } from "./IntelTab";
import { PitchTab } from "./PitchTab";
import { VoiceTab } from "./VoiceTab";
import { ReferenceTab } from "./ReferenceTab";
import type { Lead } from "@/lib/types";

interface LeadDrawerProps {
  lead: Lead | null;
}

const TABS = [
  { value: "intel", label: "INTEL" },
  { value: "pitch", label: "PITCH" },
  { value: "voice", label: "VOICE" },
  { value: "reference", label: "REF" },
] as const;

export function LeadDrawer({ lead }: LeadDrawerProps) {
  const isOpen = useDrawerStore((s) => s.isOpen);
  const close = useDrawerStore((s) => s.close);

  return (
    <AnimatePresence>
      {isOpen && lead && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            onClick={close}
            className="absolute inset-0 z-30 bg-app-void/40"
          />
          {/* Drawer */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="absolute right-0 top-0 z-40 flex h-full w-[520px] flex-col border-l border-iron bg-app-elev-2 shadow-drawer-overlay"
          >
            {/* Header */}
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-iron px-5 py-4">
              <div className="min-w-0 flex-1">
                <div className={caption}>
                  Lead · {lead._id.slice(0, 14)}…
                </div>
                <div className="mt-1 truncate font-mono text-base text-bone">
                  {lead.address}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge score={lead.scores?.composite_score ?? 0} />
                  <span className="font-mono text-xs text-mute">
                    {lead.premises_type?.toUpperCase()} · {lead.borough}
                  </span>
                </div>
              </div>
              <button
                onClick={close}
                aria-label="Close drawer"
                className="grid size-7 place-items-center rounded-[2px] border border-iron text-mute transition-colors hover:border-iron-bright hover:text-bone"
              >
                <X className="size-4" strokeWidth={1.5} />
              </button>
            </div>

            {/* Tabs */}
            <Tabs.Root defaultValue="intel" className="flex flex-1 flex-col overflow-hidden">
              <Tabs.List className="flex shrink-0 gap-0 border-b border-iron px-5">
                {TABS.map((t) => (
                  <Tabs.Trigger
                    key={t.value}
                    value={t.value}
                    className="border-b-2 border-transparent px-3 py-2.5 font-mono text-xs uppercase tracking-wide text-mute transition-colors hover:text-bone data-[state=active]:border-cyan data-[state=active]:text-cyan"
                  >
                    {t.label}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <Tabs.Content value="intel" className="outline-none">
                  <IntelTab lead={lead} />
                </Tabs.Content>
                <Tabs.Content value="pitch" className="outline-none">
                  <PitchTab lead={lead} />
                </Tabs.Content>
                <Tabs.Content value="voice" className="outline-none">
                  <VoiceTab lead={lead} />
                </Tabs.Content>
                <Tabs.Content value="reference" className="outline-none">
                  <ReferenceTab lead={lead} />
                </Tabs.Content>
              </div>
            </Tabs.Root>

            <div className={`shrink-0 border-t border-iron bg-app-surface px-5 py-2 ${caption} flex items-center gap-1.5`}>
              <kbd className="rounded-[2px] border border-iron-bright bg-app-elev-1 px-1 py-px text-bone">ESC</kbd>
              <span>close</span>
              <span className="text-iron-bright">·</span>
              <kbd className="rounded-[2px] border border-iron-bright bg-app-elev-1 px-1 py-px text-bone">TAB</kbd>
              <span>cycle tabs</span>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
