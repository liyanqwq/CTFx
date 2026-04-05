import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type ChallengeStatus } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

const STATUS_ORDER: ChallengeStatus[] = ["solved", "hoard", "working", "seen", "fetched"];
const STATUS_COLOR: Record<ChallengeStatus, string> = {
  solved: "text-green-400",
  hoard: "text-purple-300",
  working: "text-yellow-400",
  seen: "text-blue-400",
  fetched: "text-[var(--muted)]",
};

export default function CompetitionProfile() {
  const { dir = "" } = useParams();
  const { comp, setComp } = useComp();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    year: "",
    mode: "jeopardy",
    platform: "manual",
    url: "",
    flag_format: "",
    team_name: "",
    team_token: "",
    team_cookies: "",
    submit_api: false,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["info", dir],
    queryFn: () => api.getInfo(dir),
    enabled: Boolean(dir),
  });

  useEffect(() => {
    if (!data) return;
    setForm({
      name: data.name ?? "",
      year: data.year != null ? String(data.year) : "",
      mode: data.mode ?? "jeopardy",
      platform: data.platform ?? "manual",
      url: data.url ?? "",
      flag_format: data.flag_format ?? "",
      team_name: data.team_name ?? "",
      team_token: data.team_token ?? "",
      team_cookies: data.team_cookies ?? "",
      submit_api: Boolean(data.submit_api),
    });
  }, [data]);

  const activate = useMutation({
    mutationFn: async () => {
      setComp(dir);
      return api.setActiveCompetition(dir);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["competitions"] });
    },
  });

  const save = useMutation({
    mutationFn: () =>
      api.updateCompetition(dir, {
        name: form.name,
        year: Number(form.year) || undefined,
        mode: form.mode,
        platform: form.platform,
        url: form.url || null,
        flag_format: form.flag_format || null,
        team_name: form.team_name || null,
        team_token: form.team_token || null,
        team_cookies: form.team_cookies || null,
        submit_api: form.submit_api,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["info", dir] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
        queryClient.invalidateQueries({ queryKey: ["competitions"] }),
      ]);
    },
  });

  const challenges = Object.entries(data?.challenges ?? {}).map(([key, value]) => {
    const [category = "misc", name = key] = key.split("/");
    return { key, name, category, status: (value.status ?? "fetched") as ChallengeStatus, points: value.points };
  });

  const total = challenges.length;
  const solved = challenges.filter((c) => c.status === "solved").length;
  const pct = total > 0 ? Math.round((solved / total) * 100) : 0;

  const byCategory: Record<string, typeof challenges> = {};
  for (const c of challenges) {
    (byCategory[c.category] ??= []).push(c);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{data?.name ?? dir}</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {data?.year} · {data?.mode} · {data?.platform ?? "manual"}
            {data?.url && (
              <>
                {" · "}
                <a href={data.url} target="_blank" rel="noreferrer" className="underline hover:text-white">
                  {data.url}
                </a>
              </>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => activate.mutate()}
            disabled={comp === dir || activate.isPending}
            className={comp === dir ? "btn-primary opacity-60 cursor-default" : "btn-primary"}
          >
            {comp === dir ? "Active" : "Switch to this"}
          </button>
          <Link to="/competitions" className="btn-ghost">
            Back
          </Link>
        </div>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading competition...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      {data && (
        <>
          {/* Progress */}
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Progress</span>
              <span className="text-[var(--muted)]">
                {solved} / {total} solved ({pct}%)
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-[var(--border)] overflow-hidden">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              {STATUS_ORDER.map((s) => {
                const count = challenges.filter((c) => c.status === s).length;
                return (
                  <span key={s} className={cn("capitalize", STATUS_COLOR[s])}>
                    {count} {s}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Challenges by category */}
          <section className="card p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">Competition Details</h2>
              <button
                onClick={() => save.mutate()}
                disabled={save.isPending}
                className="btn-primary disabled:opacity-50"
              >
                Save
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
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
                  onChange={(e) => setForm((v) => ({ ...v, year: e.target.value }))}
                  className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
                />
              </Field>
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
                  <option value="rctf">rctf</option>
                </select>
              </Field>
              <Field label="URL">
                <input
                  value={form.url}
                  onChange={(e) => setForm((v) => ({ ...v, url: e.target.value }))}
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
              <Field label="Platform Cookies">
                <textarea
                  value={form.team_cookies}
                  onChange={(e) => setForm((v) => ({ ...v, team_cookies: e.target.value }))}
                  rows={4}
                  className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
                />
              </Field>
            </div>

            <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <input
                type="checkbox"
                checked={form.submit_api}
                onChange={(e) => setForm((v) => ({ ...v, submit_api: e.target.checked }))}
              />
              Enable platform flag submission
            </label>

            {save.error && <p className="text-sm text-red-400">{String(save.error)}</p>}
            {save.isSuccess && <p className="text-sm text-green-400">Competition updated.</p>}
          </section>

          <div className="space-y-4">
            {Object.keys(byCategory)
              .sort()
              .map((cat) => (
                <section key={cat} className="card p-5">
                  <h2 className="mb-3 text-base font-semibold capitalize">{cat}</h2>
                  <div className="space-y-1.5">
                    {byCategory[cat]
                      .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status))
                      .map((c) => (
                        <div
                          key={c.key}
                          className="flex items-center justify-between rounded border border-[var(--border)] px-3 py-2"
                        >
                          <Link
                            to={`/challenge/${cat}/${c.name}`}
                            className="font-medium hover:text-[var(--accent)] transition-colors"
                          >
                            {c.name}
                          </Link>
                          <div className="flex items-center gap-3 text-sm">
                            {c.points != null && (
                              <span className="text-[var(--muted)]">{c.points} pts</span>
                            )}
                            <span className={cn("capitalize", STATUS_COLOR[c.status])}>{c.status}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </section>
              ))}
            {total === 0 && !isLoading && (
              <div className="card p-5 text-sm text-[var(--muted)]">No challenges recorded.</div>
            )}
          </div>
        </>
      )}
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
