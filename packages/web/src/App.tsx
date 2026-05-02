import { useEffect, useMemo, useState } from "react";
import { Header, type AppMode } from "@/components/header/Header";
import { MapSlot } from "@/components/map3d/MapSlot";
import { HUDCoords } from "@/components/map3d/HUD-Coords";
import { HUDScale } from "@/components/map3d/HUD-Scale";
import { HUDLegend } from "@/components/map3d/HUD-Legend";
import {
  HUDLayerToggle,
  type LayerState,
} from "@/components/map3d/HUD-LayerToggle";
import { LeadDrawer } from "@/components/drawer/LeadDrawer";
import { CalculatorMode } from "@/components/calculator/CalculatorMode";
import { AdminCentre } from "@/components/admin/AdminCentre";
import { AtlasChartsStrip } from "@/components/charts/AtlasChartsStrip";
import { CostConfirmProvider } from "@/components/header/CostConfirmModal";
import { useLeadStore } from "@/stores/useLeadStore";
import { useDrawerStore } from "@/stores/useDrawerStore";
import { useLeadDetail, useLeads } from "@/lib/api";
import type { Lead } from "@/lib/types";

const DEFAULT_LAYERS: LayerState = {
  pins: true,
  radiance: false,
  panels: false,
  polygons: true,
};

export function App() {
  // ── ALL hooks first (cardinal rule) ────────────────────────────────────
  const [mode, setMode] = useState<AppMode>("map");
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);

  const leads = useLeadStore((s) => s.leads);
  const setLeads = useLeadStore((s) => s.setLeads);
  const selectedLeadId = useLeadStore((s) => s.selectedLeadId);
  const select = useLeadStore((s) => s.select);
  const drawerOpen = useDrawerStore((s) => s.isOpen);
  const openDrawer = useDrawerStore((s) => s.open);
  const closeDrawer = useDrawerStore((s) => s.close);

  // Bootstrap leads on mount
  const { data: bootstrap } = useLeads();
  useEffect(() => {
    if (bootstrap && bootstrap.length > 0 && leads.length === 0) {
      setLeads(bootstrap);
    }
  }, [bootstrap, leads.length, setLeads]);

  // Selected lead detail (only when drawer open)
  const detailQuery = useLeadDetail(drawerOpen ? selectedLeadId : null);

  // ESC closes drawer
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawerOpen) closeDrawer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, closeDrawer]);

  const selectedLead: Lead | null = useMemo(
    () =>
      detailQuery.data ?? leads.find((l) => l._id === selectedLeadId) ?? null,
    [detailQuery.data, leads, selectedLeadId],
  );

  const onLeadClick = (id: string) => {
    select(id);
    openDrawer();
  };

  return (
    <CostConfirmProvider>
      <div className="flex h-dvh flex-col bg-app-void text-bone">
        <Header
          mode={mode}
          onModeChange={(m) => {
            setMode(m);
            if (m !== "map") closeDrawer();
          }}
          atlasStatus="live"
        />

        {mode === "map" && (
          <main className="flex flex-1 flex-col overflow-hidden">
            <div className="relative flex-1 overflow-hidden bg-grid">
              {/* Map canvas (Luke's MapSlot) */}
              <div className="absolute inset-0">
                <MapSlot
                  leads={leads}
                  selectedLeadId={selectedLeadId}
                  onLeadClick={onLeadClick}
                  fluxOverlay={selectedLead?.flux_overlay ?? null}
                  panelLayout={selectedLead?.panel_layout ?? null}
                />
              </div>

              {/* HUD overlays — absolute-positioned within map container */}
              <HUDCoords />
              <HUDScale />
              <HUDLegend />
              <HUDLayerToggle state={layers} onChange={setLayers} />

              {/* Lead count chip */}
              <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 select-none rounded-[2px] border border-iron-bright px-2 py-1 font-mono text-xs uppercase tracking-wide text-mute"
                style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}>
                <span className="text-cyan tabular-nums">{leads.length}</span>{" "}
                LEADS · LIVE
              </div>

              {/* Drawer slides over map */}
              <LeadDrawer lead={selectedLead} />
            </div>

            <AtlasChartsStrip />
          </main>
        )}

        {mode === "calculator" && (
          <main className="flex-1 overflow-y-auto">
            <CalculatorMode />
          </main>
        )}

        {mode === "admin" && (
          <main className="flex-1 overflow-y-auto">
            <AdminCentre />
          </main>
        )}
      </div>
    </CostConfirmProvider>
  );
}
