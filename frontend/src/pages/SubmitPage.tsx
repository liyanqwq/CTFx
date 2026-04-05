import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";

export default function SubmitPage() {
  const { comp } = useComp();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState("");
  const [flag, setFlag] = useState("");

  const { data: challenges, isLoading } = useQuery({
    queryKey: ["challenge-map", comp],
    queryFn: () => api.getChallengeMap(comp),
    enabled: comp !== "unknown",
  });

  const options = useMemo(() => {
    return (challenges ?? []).slice().sort((a, b) => {
      const left = `${a.category}/${a.name}`;
      const right = `${b.category}/${b.name}`;
      return left.localeCompare(right);
    });
  }, [challenges]);

  useEffect(() => {
    if (!selected && options[0]) {
      setSelected(`${options[0].category}/${options[0].name}`);
    }
  }, [options, selected]);

  const submit = useMutation({
    mutationFn: async () => {
      const [cat, name] = selected.split("/");
      if (!cat || !name) throw new Error("Please choose a challenge");
      return api.recordFlag(comp, cat, name, flag);
    },
    onSuccess: async () => {
      setFlag("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const remoteSubmit = useMutation({
    mutationFn: async () => {
      const [cat, name] = selected.split("/");
      if (!cat || !name) throw new Error("Please choose a challenge");
      return api.submitFlag(comp, cat, name, flag);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  if (comp === "unknown") {
    return null;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="card p-5 space-y-4">
        <div>
          <h1 className="text-2xl font-bold">Submit Flag</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Record a flag locally first, then submit it separately when the competition platform is configured.
          </p>
        </div>

        <label className="block space-y-2">
          <span className="text-sm text-[var(--muted)]">Challenge</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2 outline-none focus:border-[var(--accent)]"
          >
            {options.map((challenge) => {
              const key = `${challenge.category}/${challenge.name}`;
              return (
                <option key={key} value={key}>
                  {key}
                </option>
              );
            })}
          </select>
        </label>

        <label className="block space-y-2">
          <span className="text-sm text-[var(--muted)]">Flag</span>
          <input
            value={flag}
            onChange={(e) => setFlag(e.target.value)}
            placeholder="FLAG{...}"
            className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2 outline-none focus:border-[var(--accent)]"
          />
        </label>

        <div className="grid gap-2 sm:grid-cols-2">
          <button
            onClick={() => submit.mutate()}
            disabled={!flag.trim() || !selected || submit.isPending}
            className="btn-ghost disabled:opacity-50"
          >
            Record Locally
          </button>
          <button
            onClick={() => remoteSubmit.mutate()}
            disabled={!flag.trim() || !selected || remoteSubmit.isPending}
            className="btn-primary disabled:opacity-50"
          >
            Submit to Platform
          </button>
        </div>

        {submit.error && <p className="text-sm text-red-400">{String(submit.error)}</p>}
        {submit.isSuccess && <p className="text-sm text-green-400">Flag recorded locally.</p>}
        {remoteSubmit.error && <p className="text-sm text-red-400">{String(remoteSubmit.error)}</p>}
        {remoteSubmit.isSuccess && <p className="text-sm text-green-400">Platform submission completed.</p>}
        {isLoading && <p className="text-sm text-[var(--muted)]">Loading challenge list...</p>}
      </div>

      <div className="card p-5">
        <h2 className="text-lg font-semibold">Hoarded Flags</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {options
            .filter((challenge) => challenge.status === "hoard")
            .map((challenge) => (
              <span
                key={`${challenge.category}/${challenge.name}`}
                className="rounded border border-purple-700/40 px-2 py-1 text-xs text-purple-300"
              >
                {challenge.category}/{challenge.name}
              </span>
            ))}
          {options.every((challenge) => challenge.status !== "hoard") && (
            <span className="text-sm text-[var(--muted)]">No hoarded flags yet.</span>
          )}
        </div>
      </div>

      <div className="card p-5">
        <h2 className="text-lg font-semibold">Solved Challenges</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {options
            .filter((challenge) => challenge.status === "solved")
            .map((challenge) => (
              <span
                key={`${challenge.category}/${challenge.name}`}
                className="rounded border border-green-700/40 px-2 py-1 text-xs text-green-400"
              >
                {challenge.category}/{challenge.name}
              </span>
            ))}
          {options.every((challenge) => challenge.status !== "solved") && (
            <span className="text-sm text-[var(--muted)]">No solved challenges yet.</span>
          )}
        </div>
      </div>
    </div>
  );
}
