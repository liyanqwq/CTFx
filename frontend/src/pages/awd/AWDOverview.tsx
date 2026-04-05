import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";

function inferServices(info: Awaited<ReturnType<typeof api.getInfo>> | undefined): string[] {
  if (!info) return [];
  const fromServices = info.services ? Object.keys(info.services) : [];
  if (fromServices.length > 0) return fromServices;

  const fromChallenges = Object.keys(info.challenges ?? {})
    .map((key) => key.split("/")[0])
    .filter(Boolean);

  return [...new Set(fromChallenges)].sort();
}

export default function AWDOverview() {
  const { comp } = useComp();

  const { data: info, isLoading, error } = useQuery({
    queryKey: ["info", comp],
    queryFn: () => api.getInfo(comp),
    enabled: comp !== "unknown",
  });

  const services = inferServices(info);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">AWD Services</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">Recovered service overview for AWD competitions.</p>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading services...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {services.map((service) => (
          <div key={service} className="card p-5 space-y-4">
            <div>
              <h2 className="text-lg font-semibold">{service}</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">View exploits, patches, and host map.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to={`/awd/${service}/exploits`} className="btn-ghost">
                Exploits
              </Link>
              <Link to={`/awd/${service}/patches`} className="btn-ghost">
                Patches
              </Link>
              <Link to={`/awd/${service}/hosts`} className="btn-ghost">
                Hosts
              </Link>
            </div>
          </div>
        ))}
      </div>

      {services.length === 0 && !isLoading && (
        <div className="card p-5 text-sm text-[var(--muted)]">No services were inferred from the current competition data.</div>
      )}
    </div>
  );
}
