import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  applied: "text-green-400",
  pending: "text-yellow-400",
  reverted: "text-red-400",
};

export default function AWDPatches() {
  const { comp } = useComp();
  const { service = "" } = useParams();

  const { data, isLoading, error } = useQuery({
    queryKey: ["awd-patches", comp, service],
    queryFn: () => api.listAwdPatches(comp, service),
    enabled: comp !== "unknown" && Boolean(service),
  });

  const entries = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{service} Patches</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">{entries.length} patch file{entries.length !== 1 ? "s" : ""}</p>
        </div>
        <Link to="/awd" className="btn-ghost">
          Back
        </Link>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading patches...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      <div className="space-y-3">
        {entries.map((entry, idx) => {
          const file = String(entry.file ?? "");
          const version = entry.version != null ? String(entry.version) : null;
          const status = entry.status != null ? String(entry.status) : null;
          const servicesPatched = Array.isArray(entry.services_patched)
            ? (entry.services_patched as string[])
            : null;
          const appliedAt = entry.applied_at != null ? String(entry.applied_at) : null;

          return (
            <div key={`${service}-${idx}`} className="card p-4 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono font-medium">{file}</span>
                <div className="flex items-center gap-3 text-sm">
                  {version && <span className="text-[var(--muted)]">v{version}</span>}
                  {status && (
                    <span className={cn("capitalize", STATUS_COLOR[status] ?? "text-[var(--muted)]")}>
                      {status}
                    </span>
                  )}
                </div>
              </div>
              {servicesPatched && servicesPatched.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {servicesPatched.map((s) => (
                    <span key={s} className="rounded bg-[var(--border)] px-2 py-0.5 text-xs font-mono">
                      {s}
                    </span>
                  ))}
                </div>
              )}
              {appliedAt && <p className="text-xs text-[var(--muted)]">Applied: {appliedAt}</p>}
            </div>
          );
        })}
        {entries.length === 0 && !isLoading && (
          <div className="card p-4 text-sm text-[var(--muted)]">No patch files found for this service.</div>
        )}
      </div>
    </div>
  );
}
