import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";

export default function AWDHostMap() {
  const { comp } = useComp();
  const { service = "" } = useParams();

  const { data, isLoading, error } = useQuery({
    queryKey: ["awd-hosts", comp, service],
    queryFn: () => api.listAwdHosts(comp, service),
    enabled: comp !== "unknown" && Boolean(service),
  });

  const hosts = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{service} Host Map</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {hosts.length > 0
              ? `${hosts.length} host${hosts.length !== 1 ? "s" : ""} — from hostlist.txt`
              : "Add a hostlist.txt in the service directory to populate this table."}
          </p>
        </div>
        <Link to="/awd" className="btn-ghost">
          Back
        </Link>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading hosts...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      {hosts.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--muted)]">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody>
              {hosts.map((host, idx) => (
                <tr
                  key={`${host.team}-${idx}`}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-white/5 transition-colors"
                >
                  <td className="px-4 py-2.5 text-[var(--muted)]">{idx + 1}</td>
                  <td className="px-4 py-2.5 font-medium">{host.team}</td>
                  <td className="px-4 py-2.5 font-mono">{host.ip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hosts.length === 0 && !isLoading && (
        <div className="card p-5 space-y-2">
          <p className="text-sm text-[var(--muted)]">No hosts found.</p>
          <p className="text-xs text-[var(--muted)]">
            Create <code className="font-mono">{service}/hostlist.txt</code> with one entry per line:
          </p>
          <pre className="mt-2 rounded bg-black/30 px-3 py-2 text-xs font-mono text-[var(--muted)]">
            {"team_name  192.168.1.10\nteam_name  192.168.1.11"}
          </pre>
        </div>
      )}
    </div>
  );
}
