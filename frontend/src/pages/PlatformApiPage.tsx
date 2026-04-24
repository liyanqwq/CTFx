import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type PlatformSolveEntry } from "@/lib/api";
import { useComp } from "@/lib/compContext";

function formatSolveName(entry: PlatformSolveEntry) {
  return entry.name || entry.account_name || entry.user || "?";
}

export default function PlatformApiPage() {
  const { comp } = useComp();
  const queryClient = useQueryClient();
  const [selectedChallengeId, setSelectedChallengeId] = useState<number | null>(null);

  const { data: info } = useQuery({
    queryKey: ["info", comp],
    queryFn: () => api.getInfo(comp),
    enabled: comp !== "unknown",
  });

  const enabled = comp !== "unknown" && info?.platform === "ctfd";

  const status = useQuery({
    queryKey: ["platform-status", comp],
    queryFn: () => api.getPlatformStatus(comp),
    enabled,
  });

  const challenges = useQuery({
    queryKey: ["platform-challenges", comp],
    queryFn: () => api.listPlatformChallenges(comp),
    enabled,
  });

  const scoreboard = useQuery({
    queryKey: ["platform-scoreboard", comp],
    queryFn: () => api.getPlatformScoreboard(comp),
    enabled,
  });

  useEffect(() => {
    if (!challenges.data?.length) {
      setSelectedChallengeId(null);
      return;
    }
    setSelectedChallengeId((current) => {
      if (current && challenges.data.some((item) => item.platform_id === current)) {
        return current;
      }
      return challenges.data[0].platform_id;
    });
  }, [challenges.data]);

  const solves = useQuery({
    queryKey: ["platform-solves", comp, selectedChallengeId],
    queryFn: () => api.getPlatformChallengeSolves(comp, selectedChallengeId as number),
    enabled: enabled && selectedChallengeId != null,
  });

  const scoreboardRows = useMemo(() => (scoreboard.data ?? []).slice(0, 10), [scoreboard.data]);

  if (comp === "unknown") {
    return null;
  }

  if (info && info.platform !== "ctfd") {
    return (
      <div className="card p-5 text-sm text-[var(--muted)]">
        API console is available only for competitions configured with the `ctfd` platform.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="card p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">API Console</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Inspect the configured CTFd API from the WebUI.
            </p>
          </div>
          <button
            onClick={() =>
              void Promise.all([
                queryClient.invalidateQueries({ queryKey: ["platform-status", comp] }),
                queryClient.invalidateQueries({ queryKey: ["platform-challenges", comp] }),
                queryClient.invalidateQueries({ queryKey: ["platform-scoreboard", comp] }),
                queryClient.invalidateQueries({ queryKey: ["platform-solves", comp, selectedChallengeId] }),
              ])
            }
            className="btn-primary"
          >
            Refresh
          </button>
        </div>

        {status.error && <p className="text-sm text-red-400">{String(status.error)}</p>}

        <div className="grid gap-4 md:grid-cols-4">
          <StatCard label="Auth Mode" value={status.data?.auth_mode ?? "-"} />
          <StatCard label="Challenges" value={String(status.data?.challenge_count ?? 0)} />
          <StatCard label="Solved By Me" value={String(status.data?.solved_count ?? 0)} />
          <StatCard label="Scoreboard Rows" value={String(status.data?.scoreboard_entries ?? 0)} />
        </div>

        {status.data && (
          <div className="rounded border border-[var(--border)] bg-black/20 px-4 py-3 text-sm">
            <div className="font-medium">{status.data.base_url}</div>
            <div className="mt-1 text-[var(--muted)]">
              Authenticated: {status.data.authenticated ? "yes" : "no"}
            </div>
          </div>
        )}
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <section className="card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Remote Challenges</h2>
            {challenges.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
          </div>

          {challenges.error && <p className="text-sm text-red-400">{String(challenges.error)}</p>}

          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wider text-[var(--muted)]">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Points</th>
                  <th className="px-3 py-2">Solved</th>
                </tr>
              </thead>
              <tbody>
                {(challenges.data ?? []).map((item) => (
                  <tr
                    key={item.platform_id}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-white/5 cursor-pointer"
                    onClick={() => setSelectedChallengeId(item.platform_id)}
                  >
                    <td className="px-3 py-2 font-mono">{item.platform_id}</td>
                    <td className="px-3 py-2">{item.category}</td>
                    <td className="px-3 py-2">{item.display_name || item.name}</td>
                    <td className="px-3 py-2">{item.points ?? "-"}</td>
                    <td className="px-3 py-2">{item.solved_by_me ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-6">
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Scoreboard</h2>
              {scoreboard.isLoading && <span className="text-sm text-[var(--muted)]">Loading...</span>}
            </div>

            {scoreboard.error && <p className="text-sm text-red-400">{String(scoreboard.error)}</p>}

            <div className="space-y-2">
              {scoreboardRows.map((item, index) => (
                <div
                  key={`${item.name ?? item.account_name ?? item.team ?? "entry"}-${index}`}
                  className="flex items-center justify-between rounded border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <span>
                    {index + 1}. {item.name || item.account_name || item.team || "?"}
                  </span>
                  <span className="text-[var(--muted)]">{item.score ?? item.value ?? 0}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Challenge Solves</h2>
              <select
                value={selectedChallengeId ?? ""}
                onChange={(e) => setSelectedChallengeId(Number(e.target.value) || null)}
                className="rounded border border-[var(--border)] bg-black/20 px-3 py-2 text-sm"
              >
                {(challenges.data ?? []).map((item) => (
                  <option key={item.platform_id} value={item.platform_id}>
                    {item.platform_id} - {item.display_name || item.name}
                  </option>
                ))}
              </select>
            </div>

            {solves.error && <p className="text-sm text-red-400">{String(solves.error)}</p>}
            {solves.isLoading && <p className="text-sm text-[var(--muted)]">Loading solves...</p>}

            <div className="space-y-2">
              {(solves.data ?? []).map((item, index) => (
                <div
                  key={`${formatSolveName(item)}-${item.date ?? item.created ?? index}`}
                  className="rounded border border-[var(--border)] px-3 py-2 text-sm"
                >
                  <div className="font-medium">{formatSolveName(item)}</div>
                  <div className="mt-1 text-[var(--muted)]">{item.date || item.created || "-"}</div>
                </div>
              ))}
              {!solves.isLoading && (solves.data ?? []).length === 0 && (
                <p className="text-sm text-[var(--muted)]">No solve records returned.</p>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wider text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}
