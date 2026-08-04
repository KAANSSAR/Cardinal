import { useEffect, useState } from "react";
import { fetchSectorHeatmap, type SectorPerformance } from "../lib/api";

function tileClasses(changePct: number): string {
  const abs = Math.abs(changePct);
  if (changePct > 0) {
    return abs > 0.015
      ? "bg-term-accent-2/20 border-term-accent-2/40 text-term-accent-2"
      : "bg-term-accent-2/10 border-term-accent-2/20 text-term-accent-2";
  }
  if (changePct < 0) {
    return abs > 0.015
      ? "bg-term-danger/20 border-term-danger/40 text-term-danger"
      : "bg-term-danger/10 border-term-danger/20 text-term-danger";
  }
  return "bg-term-panel-alt border-term-border text-term-text-dim";
}

export default function SectorHeatmap() {
  const [sectors, setSectors] = useState<SectorPerformance[] | null>(null);

  useEffect(() => {
    fetchSectorHeatmap()
      .then((data) => setSectors(data.sectors))
      .catch(() => setSectors([]));
  }, []);

  return (
    <div className="rounded-lg border border-term-border bg-term-panel p-5 h-full flex flex-col">
      <p className="font-mono text-[10px] text-term-text-faint uppercase tracking-widest mb-4">
        Sector Heatmap
      </p>
      {sectors === null ? (
        <div className="flex-1 animate-pulse bg-term-panel-alt rounded" />
      ) : (
        <div className="grid grid-cols-5 gap-2 flex-1">
          {sectors.map((s) => (
            <div
              key={s.etf_proxy}
              className={`rounded-md border flex flex-col items-center justify-center text-center px-2 py-3 ${tileClasses(s.change_pct)}`}
            >
              <p className="text-[11px] font-medium leading-tight">{s.name}</p>
              <p className="font-mono text-xs font-semibold mt-1">
                {s.change_pct >= 0 ? "+" : ""}
                {(s.change_pct * 100).toFixed(1)}%
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}