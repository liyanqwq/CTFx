import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type ChallengeRecord } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

type Bucket = "hoarding" | "submitted" | "doing";

function getBucket(challenge: ChallengeRecord): Bucket {
  if (challenge.status === "solved") return "submitted";
  if (challenge.status === "hoard") return "hoarding";
  return "doing";
}

const BUCKET_LABEL: Record<Bucket, string> = {
  hoarding: "Hoarding",
  submitted: "Submitted",
  doing: "Doing",
};

const BUCKET_COLOR: Record<Bucket, string> = {
  hoarding: "text-purple-300",
  submitted: "text-green-400",
  doing: "text-yellow-300",
};

export default function FlagsPage() {
  const { comp } = useComp();

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ["challenge-map", comp],
    queryFn: () => api.getChallengeMap(comp),
    enabled: comp !== "unknown",
  });

  const rows = useMemo(() => {
    return (challenges ?? [])
      .map((challenge) => ({
        ...challenge,
        bucket: getBucket(challenge),
      }))
      .sort((a, b) => {
        const left = `${a.bucket}-${a.category}/${a.name}`;
        const right = `${b.bucket}-${b.category}/${b.name}`;
        return left.localeCompare(right);
      });
  }, [challenges]);

  const stats = useMemo(() => {
    return {
      hoarding: rows.filter((row) => row.bucket === "hoarding").length,
      submitted: rows.filter((row) => row.bucket === "submitted").length,
      doing: rows.filter((row) => row.bucket === "doing").length,
    };
  }, [rows]);

  if (comp === "unknown") return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Flags</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Overview of local hoarding, submitted flags, and challenges still in progress.
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard label="Hoarding" value={String(stats.hoarding)} tone="text-purple-300" />
        <StatCard label="Submitted" value={String(stats.submitted)} tone="text-green-400" />
        <StatCard label="Doing" value={String(stats.doing)} tone="text-yellow-300" />
      </section>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading flags...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      <section className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--muted)]">
              <th className="px-4 py-3">Challenge</th>
              <th className="px-4 py-3">Bucket</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Flag</th>
              <th className="px-4 py-3">Remote</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.category}/${row.name}`} className="border-b border-[var(--border)] last:border-0">
                <td className="px-4 py-3">
                  <Link to={`/challenge/${row.category}/${row.name}`} className="hover:text-[var(--accent)]">
                    {row.category}/{row.name}
                  </Link>
                </td>
                <td className={cn("px-4 py-3 font-medium", BUCKET_COLOR[row.bucket])}>{BUCKET_LABEL[row.bucket]}</td>
                <td className="px-4 py-3 capitalize">{row.status}</td>
                <td className="px-4 py-3 font-mono text-xs">{row.flag || "-"}</td>
                <td className="px-4 py-3 text-[var(--muted)]">{row.remote || "-"}</td>
              </tr>
            ))}
            {rows.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-[var(--muted)]">
                  No challenge records yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wider text-[var(--muted)]">{label}</p>
      <p className={cn("mt-2 text-2xl font-bold", tone)}>{value}</p>
    </div>
  );
}
