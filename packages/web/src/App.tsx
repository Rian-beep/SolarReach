import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Header, type AppMode } from "@/components/header/Header";
import { MapSlot } from "@/components/map3d/MapSlot";
import { RadianceCanvas } from "@/components/map3d/RadianceCanvas";
import { HUDCoords } from "@/components/map3d/HUD-Coords";
import { HUDScale } from "@/components/map3d/HUD-Scale";
import { HUDLegend } from "@/components/map3d/HUD-Legend";
import {
  HUDLayerToggle,
  type LayerDataCounts,
  type LayerState,
} from "@/components/map3d/HUD-LayerToggle";
import { LeadDrawer } from "@/components/drawer/LeadDrawer";
import { CalculatorMode } from "@/components/calculator/CalculatorMode";
import { AdminCentre } from "@/components/admin/AdminCentre";
import { AtlasChartsStrip } from "@/components/charts/AtlasChartsStrip";
import { CostConfirmProvider } from "@/components/header/CostConfirmModal";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useLeadStore } from "@/stores/useLeadStore";
import { useDrawerStore } from "@/stores/useDrawerStore";
import { useSearchStore } from "@/stores/useSearchStore";
import {
  useFluxOverlay,
  useLeadDetail,
  useLeads,
  usePanels,
} from "@/lib/api";
import type { Lead } from "@/lib/types";

// Auto-scan default — boot the camera straight to central London so the demo
// lands on visible pins without the user typing a postcode. EC1Y 8AF =
// Barbican / Old Street tech corridor (placeholder of the input field too).
const DEFAULT_SCAN = {
  postcode: "EC1Y 8AF",
  lat: 51.5256,
  lng: -0.0876,
} as const;
// Camera flight from UK overview → London is ~1500ms; nudge the leads in
// half-way so pins materialise during the descent rather than popping in
// after the camera lands.
const AUTOSCAN_LEADS_DELAY_MS = 500;

const DEFAULT_LAYERS: LayerState = {
  pins: true,
  radiance: true, // heat overlay on by default — read across the whole map
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

  // ── Auto-scan on first paint ────────────────────────────────────────────
  // Fly the camera to the default postcode (EC1Y 8AF) the moment the app
  // mounts — no /scan POST, just a search-target nudge that MapSlot picks up
  // and a delayed lead push so pins stream in mid-flight. This avoids the
  // "blank UK overview" dead state on first load.
  const setSearchTarget = useSearchStore((s) => s.setTarget);
  const autoScanFiredRef = useRef(false);
  useEffect(() => {
    if (autoScanFiredRef.current) return;
    autoScanFiredRef.current = true;
    setSearchTarget({ ...DEFAULT_SCAN });
    // If bootstrap leads already resolved by mount (cached), seed them after
    // the camera has begun its flight so pins appear during the descent. If
    // bootstrap hasn't resolved yet, the effect above takes over once it does.
    const t = setTimeout(() => {
      if (bootstrap && bootstrap.length > 0) {
        setLeads(bootstrap);
      }
    }, AUTOSCAN_LEADS_DELAY_MS);
    return () => clearTimeout(t);
    // Mount-only — intentionally ignore bootstrap/setLeads churn here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // ── Auto-fetch flux + panels on lead select ─────────────────────────────
  // Live Solar API renders are <10¢ each (cardinal rule 4 only fires the
  // cost-confirm modal at ≥£0.10). Skip if the lead doc already carries the
  // overlay/layout (cached server-side). Track which lead ids we've already
  // kicked off in this session to avoid re-firing if the lead doc lacks the
  // field temporarily (e.g. a flux call that returned but hasn't propagated).
  const flux = useFluxOverlay();
  const panels = usePanels();
  const qc = useQueryClient();
  const fetchedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const id = selectedLead?._id;
    if (!id) return;
    if (fetchedRef.current.has(id)) return;

    const needsFlux = !selectedLead.flux_overlay?.url;
    const needsPanels = !selectedLead.panel_layout?.panel_count;
    if (!needsFlux && !needsPanels) return;

    fetchedRef.current.add(id);

    const jobs: Promise<unknown>[] = [];
    if (needsFlux) jobs.push(flux.mutateAsync(id).catch(() => null));
    if (needsPanels) jobs.push(panels.mutateAsync(id).catch(() => null));

    // Once either lands, refresh the lead detail so the persisted
    // flux_overlay / panel_layout flow back into the drawer + map.
    Promise.allSettled(jobs).then(() => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
    });
    // Intentionally don't depend on `flux` / `panels` / `qc` (stable refs from
    // hook factories) — keying purely off `selectedLead._id` is what we want.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLead?._id, selectedLead?.flux_overlay?.url, selectedLead?.panel_layout?.panel_count]);

  const onLeadClick = (id: string) => {
    select(id);
    openDrawer();
  };

  // Per-layer data coverage. Drives the ·n/total live HUD chip so the
  // RADIANCE/PANELS toggles reflect dataset coverage (e.g. "13/264 live"
  // for the EC2M cached flux set) instead of the single-selection state.
  const layerData = useMemo<LayerDataCounts>(
    () => ({
      pins: leads.length, // pins always render off the base lead doc
      polygons: leads.length, // rooftop polygons always render
      radiance: leads.filter((l) => !!l.flux_overlay?.url).length,
      panels: leads.filter((l) => (l.panel_layout?.panels?.length ?? 0) > 0)
        .length,
    }),
    [leads],
  );

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
              {/* Map canvas (Luke's MapSlot) — wrapped so a Maps SDK crash
                  doesn't black-screen the rest of the cockpit. */}
              <div className="absolute inset-0">
                <ErrorBoundary scope="map">
                  <MapSlot
                    leads={leads}
                    selectedLeadId={selectedLeadId}
                    onLeadClick={onLeadClick}
                    fluxOverlay={selectedLead?.flux_overlay ?? null}
                    panelLayout={selectedLead?.panel_layout ?? null}
                    layers={layers}
                  />
                </ErrorBoundary>
              </div>

              {/* Global RADIANCE heatmap — inferno blobs at every lead's
                  geo location, camera-coupled. Sits above the 3D scene
                  (z-10) but below the HUD overlays (z-20+). Toggled by
                  the RADIANCE layer chip. */}
              <ErrorBoundary scope="radiance-canvas">
                <RadianceCanvas enabled={layers.radiance} />
              </ErrorBoundary>

              {/* HUD overlays — absolute-positioned within map container */}
              <ErrorBoundary scope="hud">
                <HUDCoords />
                <HUDScale />
                <HUDLegend />
                <HUDLayerToggle
                  state={layers}
                  onChange={setLayers}
                  totalLeads={leads.length}
                  dataAvailable={layerData}
                />
              </ErrorBoundary>

              {/* Lead count chip */}
              <div
                className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 select-none rounded-[2px] border border-iron-bright px-2 py-1 font-mono text-xs uppercase tracking-wide text-mute"
                style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}
              >
                <span className="text-cyan tabular-nums">{leads.length}</span>{" "}
                LEADS · LIVE
              </div>

              {/* Drawer slides over map */}
              <ErrorBoundary scope="drawer">
                <LeadDrawer lead={selectedLead} />
              </ErrorBoundary>
            </div>

            <ErrorBoundary scope="charts">
              <AtlasChartsStrip />
            </ErrorBoundary>
          </main>
        )}

        {mode === "calculator" && (
          <main className="flex-1 overflow-y-auto">
            <ErrorBoundary scope="calculator">
              <CalculatorMode />
            </ErrorBoundary>
          </main>
        )}

        {mode === "admin" && (
          <main className="flex-1 overflow-y-auto">
            <ErrorBoundary scope="admin">
              <AdminCentre />
            </ErrorBoundary>
          </main>
        )}
      </div>
    </CostConfirmProvider>
  );
}
