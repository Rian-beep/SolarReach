interface HUDScaleProps {
  className?: string;
}

export function HUDScale({ className }: HUDScaleProps) {
  return (
    <div
      className={
        "absolute top-3 right-3 z-20 rounded-[2px] border border-iron-bright px-2 py-1 font-mono text-xs " +
        (className ?? "")
      }
      style={{ backgroundColor: "rgba(10, 14, 20, 0.8)" }}
    >
      <div className="text-grid uppercase tracking-wide mb-1">SCALE</div>
      <div className="flex items-end gap-px h-3">
        {[
          { w: "w-12", label: "1km" },
          { w: "w-8", label: "500m" },
          { w: "w-4", label: "100m" },
        ].map((s) => (
          <div key={s.label} className="flex flex-col items-center gap-px">
            <div className={"h-1 " + s.w + " bg-iron-bright"} />
            <span className="text-dim tabular-nums leading-none">
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
