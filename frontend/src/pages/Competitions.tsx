import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

export default function Competitions() {
  const { comp, setComp } = useComp();
  const queryClient = useQueryClient();
  const [yearFilter, setYearFilter] = useState<number | null>(null);
  const [form, setForm] = useState({
    name: "",
    year: new Date().getFullYear(),
    mode: "jeopardy",
    platform: "manual",
    url: "",
    team_name: "",
    team_token: "",
    flag_format: "",
  });

  const { data: competitions, isLoading, error } = useQuery({
    queryKey: ["competitions"],
    queryFn: () => api.listCompetitions(),
  });

  const years = useMemo(() => {
    const set = new Set((competitions ?? []).map((c) => c.year));
    return Array.from(set).sort((a, b) => b - a);
  }, [competitions]);

  const filtered = useMemo(() => {
    if (!yearFilter) return competitions ?? [];
    return (competitions ?? []).filter((c) => c.year === yearFilter);
  }, [competitions, yearFilter]);

  const createCompetition = useMutation({
    mutationFn: () =>
      api.createCompetition({
        ...form,
        url: form.url || undefined,
        team_name: form.team_name || undefined,
        team_token: form.team_token || undefined,
        flag_format: form.flag_format || undefined,
      }),
    onSuccess: async (created) => {
      setComp(created.dir);
      await api.setActiveCompetition(created.dir).catch(() => undefined);
      await queryClient.invalidateQueries({ queryKey: ["competitions"] });
      setForm({
        name: "",
        year: new Date().getFullYear(),
        mode: "jeopardy",
        platform: "manual",
        url: "",
        team_name: "",
        team_token: "",
        flag_format: "",
      });
    },
  });

  const activateCompetition = useMutation({
    mutationFn: async (dir: string) => {
      setComp(dir);
      return api.setActiveCompetition(dir);
    },
    onSuccess: async (_, dir) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["competitions"] }),
        queryClient.invalidateQueries({ queryKey: ["info", dir] }),
      ]);
    },
  });

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_420px]">
      <section className="card p-5 space-y-4">
        <div>
          <h1 className="text-2xl font-bold">Competitions</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Switch active workspaces or inspect an existing competition profile.
          </p>
        </div>

        {/* Year filter */}
        {years.length > 1 && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setYearFilter(null)}
              className={cn("btn-ghost text-sm px-3 py-1", !yearFilter && "bg-[var(--accent)] text-white")}
            >
              All
            </button>
            {years.map((y) => (
              <button
                key={y}
                onClick={() => setYearFilter(y === yearFilter ? null : y)}
                className={cn(
                  "btn-ghost text-sm px-3 py-1",
                  yearFilter === y && "bg-[var(--accent)] text-white"
                )}
              >
                {y}
              </button>
            ))}
          </div>
        )}

        {isLoading && <p className="text-sm text-[var(--muted)]">Loading competitions...</p>}
        {error && <p className="text-sm text-red-400">{String(error)}</p>}

        <div className="space-y-3">
          {filtered.map((item) => {
            const pct = item.total > 0 ? Math.round((item.solved / item.total) * 100) : 0;
            return (
              <div key={item.dir} className="rounded border border-[var(--border)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-semibold truncate">
                      {item.name} {item.year}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {item.mode} · {item.solved}/{item.total} solved
                    </p>
                    {item.total > 0 && (
                      <div className="mt-2 h-1.5 w-full max-w-[200px] rounded-full bg-[var(--border)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[var(--accent)]"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => activateCompetition.mutate(item.dir)}
                      className={item.dir === comp ? "btn-primary" : "btn-ghost"}
                    >
                      {item.dir === comp ? "Active" : "Use"}
                    </button>
                    <Link to={`/competitions/${item.dir}`} className="btn-ghost">
                      Open
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}

          {filtered.length === 0 && !isLoading && (
            <p className="text-sm text-[var(--muted)]">No competitions found.</p>
          )}
        </div>
      </section>

      <section className="card p-5 space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Create Competition</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Initialize a new local competition workspace.</p>
        </div>

        <Field label="Name">
          <input
            value={form.name}
            onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <Field label="Year">
          <input
            type="number"
            value={form.year}
            onChange={(e) => setForm((v) => ({ ...v, year: Number(e.target.value) || new Date().getFullYear() }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Mode">
            <select
              value={form.mode}
              onChange={(e) => setForm((v) => ({ ...v, mode: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            >
              <option value="jeopardy">jeopardy</option>
              <option value="awd">awd</option>
            </select>
          </Field>

          <Field label="Platform">
            <select
              value={form.platform}
              onChange={(e) => setForm((v) => ({ ...v, platform: e.target.value }))}
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
            >
              <option value="manual">manual</option>
              <option value="ctfd">ctfd</option>
            </select>
          </Field>
        </div>

        <Field label="URL">
          <input
            value={form.url}
            onChange={(e) => setForm((v) => ({ ...v, url: e.target.value }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <Field label="Team Name">
          <input
            value={form.team_name}
            onChange={(e) => setForm((v) => ({ ...v, team_name: e.target.value }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <Field label="Team Token">
          <input
            type="password"
            value={form.team_token}
            onChange={(e) => setForm((v) => ({ ...v, team_token: e.target.value }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <Field label="Flag Format">
          <input
            value={form.flag_format}
            onChange={(e) => setForm((v) => ({ ...v, flag_format: e.target.value }))}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
          />
        </Field>

        <button
          onClick={() => createCompetition.mutate()}
          disabled={!form.name.trim() || createCompetition.isPending}
          className="btn-primary disabled:opacity-50"
        >
          Create
        </button>

        {createCompetition.error && <p className="text-sm text-red-400">{String(createCompetition.error)}</p>}
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      {children}
    </label>
  );
}
