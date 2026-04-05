import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus, Terminal, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

const DEFAULT_CATEGORIES = ["pwn", "crypto", "web", "forensics", "rev", "misc"];

export default function Dashboard() {
  const { comp } = useComp();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    category: "misc",
    name: "",
    points: "",
    remote: "",
    description: "",
  });

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ["challenge-map", comp],
    queryFn: () => api.getChallengeMap(comp),
    enabled: comp !== "unknown",
  });

  const addChallenge = useMutation({
    mutationFn: () =>
      api.addChallenge(comp, {
        category: form.category,
        name: form.name.trim(),
        points: form.points.trim() ? Number(form.points) : undefined,
        remote: form.remote.trim() || undefined,
        description: form.description.trim() || undefined,
      }),
    onSuccess: async () => {
      setForm({
        category: "misc",
        name: "",
        points: "",
        remote: "",
        description: "",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const deleteChallenge = useMutation({
    mutationFn: ({ cat, name }: { cat: string; name: string }) => api.deleteChallenge(comp, cat, name),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const grouped = useMemo(() => {
    const map = new Map<string, typeof challenges>();
    for (const challenge of challenges ?? []) {
      const current = map.get(challenge.category) ?? [];
      current.push(challenge);
      map.set(challenge.category, current);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [challenges]);

  const stats = useMemo(() => {
    const items = challenges ?? [];
    return {
      total: items.length,
      solved: items.filter((item) => item.status === "solved").length,
      working: items.filter((item) => item.status === "working").length,
      hoard: items.filter((item) => item.status === "hoard").length,
    };
  }, [challenges]);

  if (comp === "unknown") {
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="card p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Add Challenge</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Create a new challenge directly from the dashboard.</p>
          </div>
          <button
            onClick={() => addChallenge.mutate()}
            disabled={!form.name.trim() || addChallenge.isPending}
            className="btn-primary disabled:opacity-50 inline-flex items-center gap-2"
          >
            <Plus size={14} />
            Add
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <label className="block space-y-1.5">
            <span className="text-sm text-[var(--muted)]">Category</span>
            <select
              value={form.category}
              onChange={(e) => setForm((v) => ({ ...v, category: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            >
              {DEFAULT_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-[var(--muted)]">Name</span>
            <input
              value={form.name}
              onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-[var(--muted)]">Points</span>
            <input
              type="number"
              value={form.points}
              onChange={(e) => setForm((v) => ({ ...v, points: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm text-[var(--muted)]">Remote</span>
            <input
              value={form.remote}
              onChange={(e) => setForm((v) => ({ ...v, remote: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            />
          </label>

          <label className="block space-y-1.5 md:col-span-2 xl:col-span-1">
            <span className="text-sm text-[var(--muted)]">Description</span>
            <input
              value={form.description}
              onChange={(e) => setForm((v) => ({ ...v, description: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            />
          </label>
        </div>

        {addChallenge.error && <p className="text-sm text-red-400">{String(addChallenge.error)}</p>}
        {addChallenge.isSuccess && <p className="text-sm text-green-400">Challenge created.</p>}
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <StatCard label="Total Challenges" value={String(stats.total)} />
        <StatCard label="Solved" value={String(stats.solved)} />
        <StatCard label="Working" value={String(stats.working)} />
        <StatCard label="Hoard" value={String(stats.hoard)} />
      </section>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading challenges...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      <div className="space-y-5">
        {grouped.map(([category, items]) => (
          <section key={category} className="space-y-3">
            <div className="flex items-center gap-2">
              <FolderOpen size={16} className="text-[var(--accent)]" />
              <h2 className="text-lg font-semibold capitalize">{category}</h2>
              <span className="text-xs text-[var(--muted)]">{items?.length ?? 0} items</span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {(items ?? []).map((challenge) => (
                <Link
                  key={`${challenge.category}/${challenge.name}`}
                  to={`/challenge/${challenge.category}/${challenge.name}`}
                  className="card p-4 hover:border-[var(--accent)] transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold">{challenge.name}</h3>
                      <p className="mt-1 text-xs text-[var(--muted)]">
                        {challenge.points ? `${challenge.points} pts` : "No points set"}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "rounded border px-2 py-0.5 text-xs uppercase tracking-wide",
                        challenge.status === "solved" && "border-green-700/50 text-green-400",
                        challenge.status === "hoard" && "border-purple-700/50 text-purple-300",
                        challenge.status === "working" && "border-yellow-700/50 text-yellow-400",
                        challenge.status === "seen" && "border-blue-700/50 text-blue-400",
                        challenge.status === "fetched" && "border-slate-700/50 text-slate-400"
                      )}
                    >
                      {challenge.status}
                    </span>
                  </div>

                  {challenge.remote && (
                    <div className="mt-3 flex items-start gap-2 rounded bg-black/20 px-2 py-1.5 text-xs text-[var(--muted)]">
                      <Terminal size={12} className="mt-0.5 shrink-0" />
                      <span className="break-all">{challenge.remote}</span>
                    </div>
                  )}

                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (window.confirm(`Delete ${challenge.category}/${challenge.name}?`)) {
                          deleteChallenge.mutate({ cat: challenge.category, name: challenge.name });
                        }
                      }}
                      disabled={deleteChallenge.isPending}
                      className="btn-ghost inline-flex items-center gap-2 text-red-300 hover:text-red-200"
                    >
                      <Trash2 size={14} />
                      Delete
                    </button>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ))}
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
