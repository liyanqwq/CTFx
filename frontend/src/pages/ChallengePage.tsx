import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import MDEditor from "@uiw/react-md-editor";
import { useParams } from "react-router-dom";
import { Download, FileText, PenLine, Play, Save } from "lucide-react";
import { api, type ChallengeStatus } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

const STATUSES: ChallengeStatus[] = ["fetched", "seen", "working", "hoard", "solved"];

type Tab = "description" | "writeup";

export default function ChallengePage() {
  const { cat = "", name = "" } = useParams();
  const { comp } = useComp();
  const queryClient = useQueryClient();
  const [flag, setFlag] = useState("");
  const [tab, setTab] = useState<Tab>("description");
  const [descEditing, setDescEditing] = useState(false);
  const [chalDraft, setChalDraft] = useState<string>("");
  const [wpDraft, setWpDraft] = useState<string>("");
  const [metaDraft, setMetaDraft] = useState({
    points: "",
    remote: "",
    extra_info: "",
  });

  const { data: challenge, isLoading, error } = useQuery({
    queryKey: ["challenge", comp, cat, name],
    queryFn: () => api.getChallenge(comp, cat, name),
    enabled: comp !== "unknown" && Boolean(cat) && Boolean(name),
  });

  const { data: chalMd, isLoading: chalMdLoading } = useQuery({
    queryKey: ["chal-md", comp, cat, name],
    queryFn: () => api.getChalMd(comp, cat, name),
    enabled: comp !== "unknown" && Boolean(cat) && Boolean(name),
  });

  const { data: wpMd } = useQuery({
    queryKey: ["wp-md", comp, cat, name],
    queryFn: () => api.getWpMd(comp, cat, name),
    enabled: comp !== "unknown" && Boolean(cat) && Boolean(name),
  });

  const { data: attachments } = useQuery({
    queryKey: ["attachments", comp, cat, name],
    queryFn: () => api.listChallengeAttachments(comp, cat, name),
    enabled: comp !== "unknown" && Boolean(cat) && Boolean(name),
  });

  useEffect(() => {
    if (chalMd !== undefined) {
      setChalDraft(chalMd);
    }
  }, [chalMd]);

  useEffect(() => {
    if (wpMd !== undefined) {
      setWpDraft(wpMd);
    }
  }, [wpMd]);

  useEffect(() => {
    if (!challenge) return;
    setMetaDraft({
      points: challenge.points != null ? String(challenge.points) : "",
      remote: challenge.remote ?? "",
      extra_info: challenge.extra_info ?? "",
    });
  }, [challenge]);

  const updateStatus = useMutation({
    mutationFn: (status: ChallengeStatus) => api.updateChallengeStatus(comp, cat, name, status),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge", comp, cat, name] }),
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const saveFlag = useMutation({
    mutationFn: () => api.recordFlag(comp, cat, name, flag),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge", comp, cat, name] }),
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const submitFlag = useMutation({
    mutationFn: () => api.submitFlag(comp, cat, name, flag),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge", comp, cat, name] }),
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  const runExploit = useMutation({
    mutationFn: () => api.runExploit(comp, cat, name),
  });

  const saveChal = useMutation({
    mutationFn: () => api.putChalMd(comp, cat, name, chalDraft),
    onSuccess: async () => {
      setDescEditing(false);
      await queryClient.invalidateQueries({ queryKey: ["chal-md", comp, cat, name] });
    },
  });

  const saveWp = useMutation({
    mutationFn: () => api.putWpMd(comp, cat, name, wpDraft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["wp-md", comp, cat, name] });
    },
  });

  const saveMeta = useMutation({
    mutationFn: () =>
      api.updateChallengeMeta(comp, cat, name, {
        points: metaDraft.points.trim() ? Number(metaDraft.points) : null,
        remote: metaDraft.remote.trim() || null,
        extra_info: metaDraft.extra_info.trim() || null,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["challenge", comp, cat, name] }),
        queryClient.invalidateQueries({ queryKey: ["challenge-map", comp] }),
        queryClient.invalidateQueries({ queryKey: ["info", comp] }),
      ]);
    },
  });

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (tab === "description" && descEditing) {
          saveChal.mutate();
          return;
        }
        if (tab === "writeup") {
          saveWp.mutate();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [descEditing, saveChal, saveWp, tab]);

  const markdown = useMemo(() => {
    if (chalDraft.trim()) return chalDraft;
    if (challenge?.description?.trim()) return challenge.description;
    return `# ${name}\n\nNo challenge description is currently available.`;
  }, [chalDraft, challenge?.description, name]);

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-[var(--muted)]">{cat || "challenge"}</p>
            <h1 className="mt-1 text-2xl font-bold">{name}</h1>
            {challenge?.remote && <p className="mt-2 text-sm text-[var(--muted)]">{challenge.remote}</p>}
            {challenge?.points != null && (
              <p className="mt-1 text-sm font-medium text-[var(--accent)]">{challenge.points} pts</p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => updateStatus.mutate(s)}
                className={cn(
                  "btn border border-[var(--border)] capitalize",
                  challenge?.status === s ? "bg-[var(--accent)] text-white" : "btn-ghost"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-0">
          {/* Tabs */}
          <div className="flex gap-1 border-b border-[var(--border)] pb-0">
            <TabBtn icon={<FileText size={14} />} label="Description" active={tab === "description"} onClick={() => setTab("description")} />
            <TabBtn icon={<PenLine size={14} />} label="Writeup" active={tab === "writeup"} onClick={() => setTab("writeup")} />
          </div>

          {tab === "description" && (
            <div className="card rounded-tl-none p-5 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-[var(--muted)]">
                  {descEditing ? "Editing challenge description" : "Challenge description"}
                </span>
                <div className="flex gap-2">
                  {descEditing && (
                    <button
                      onClick={() => {
                        setChalDraft(chalMd ?? "");
                        setDescEditing(false);
                      }}
                      className="btn-ghost"
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    onClick={() => (descEditing ? saveChal.mutate() : setDescEditing(true))}
                    disabled={saveChal.isPending}
                    className="btn-primary disabled:opacity-50"
                  >
                    {descEditing ? "Save" : "Edit"}
                  </button>
                </div>
              </div>

              {isLoading || chalMdLoading ? (
                <p>Loading challenge...</p>
              ) : error ? (
                <p className="text-red-400">{String(error)}</p>
              ) : descEditing ? (
                <div data-color-mode="dark" className="space-y-3">
                  <MDEditor value={chalDraft} onChange={(v) => setChalDraft(v ?? "")} height={480} preview="live" />
                  <p className="text-sm text-[var(--muted)]">Ctrl+S to save the description.</p>
                </div>
              ) : (
                <article className="prose prose-invert max-w-none prose-pre:bg-black/40 prose-code:text-slate-200">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
                </article>
              )}

              {saveChal.error && <p className="text-sm text-red-400">{String(saveChal.error)}</p>}
              {saveChal.isSuccess && <p className="text-sm text-green-400">Description saved.</p>}
            </div>
          )}

          {tab === "writeup" && (
            <div className="card rounded-tl-none p-4 space-y-3" data-color-mode="dark">
              <MDEditor
                value={wpDraft}
                onChange={(v) => setWpDraft(v ?? "")}
                height={480}
                preview="live"
              />
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--muted)]">Ctrl+S to save</span>
                <button
                  onClick={() => saveWp.mutate()}
                  disabled={saveWp.isPending}
                  className="btn-primary disabled:opacity-50 inline-flex items-center gap-2"
                >
                  <Save size={14} />
                  Save
                </button>
              </div>
              {saveWp.error && <p className="text-sm text-red-400">{String(saveWp.error)}</p>}
              {saveWp.isSuccess && <p className="text-sm text-green-400">Saved.</p>}
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Extra Info</h2>
              <button
                onClick={() => saveMeta.mutate()}
                disabled={saveMeta.isPending}
                className="btn-primary disabled:opacity-50"
              >
                Save
              </button>
            </div>

            <label className="block space-y-1.5">
              <span className="text-sm text-[var(--muted)]">Points</span>
              <input
                type="number"
                value={metaDraft.points}
                onChange={(e) => setMetaDraft((v) => ({ ...v, points: e.target.value }))}
                className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
              />
            </label>

            <label className="block space-y-1.5">
              <span className="text-sm text-[var(--muted)]">Remote</span>
              <input
                value={metaDraft.remote}
                onChange={(e) => setMetaDraft((v) => ({ ...v, remote: e.target.value }))}
                className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
              />
            </label>

            <label className="block space-y-1.5">
              <span className="text-sm text-[var(--muted)]">Notes</span>
              <textarea
                value={metaDraft.extra_info}
                onChange={(e) => setMetaDraft((v) => ({ ...v, extra_info: e.target.value }))}
                rows={5}
                className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2"
              />
            </label>

            {saveMeta.error && <p className="text-sm text-red-400">{String(saveMeta.error)}</p>}
            {saveMeta.isSuccess && <p className="text-sm text-green-400">Extra info updated.</p>}
          </div>

          <div className="card p-5 space-y-3">
            <h2 className="text-lg font-semibold">Flag</h2>
            <input
              value={flag}
              onChange={(e) => setFlag(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && flag.trim() && saveFlag.mutate()}
              placeholder="FLAG{...}"
              className="w-full rounded border border-[var(--border)] bg-black/20 px-3 py-2 outline-none focus:border-[var(--accent)]"
            />
            <p className="text-sm text-[var(--muted)]">
              Save records the flag locally and moves the challenge to `hoard`. Submit sends it to the configured platform.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                onClick={() => saveFlag.mutate()}
                disabled={!flag.trim() || saveFlag.isPending}
                className="btn-ghost w-full disabled:opacity-50"
              >
                <span className="inline-flex items-center gap-2">
                  <Save size={14} />
                  Save Local
                </span>
              </button>
              <button
                onClick={() => submitFlag.mutate()}
                disabled={!flag.trim() || submitFlag.isPending}
                className="btn-primary w-full disabled:opacity-50"
              >
                <span className="inline-flex items-center gap-2">
                  <Save size={14} />
                  Submit Flag
                </span>
              </button>
            </div>
            {saveFlag.error && <p className="text-sm text-red-400">{String(saveFlag.error)}</p>}
            {saveFlag.isSuccess && <p className="text-sm text-green-400">Flag recorded locally.</p>}
            {submitFlag.error && <p className="text-sm text-red-400">{String(submitFlag.error)}</p>}
            {submitFlag.isSuccess && <p className="text-sm text-green-400">Submission request completed.</p>}
          </div>

          <div className="card p-5 space-y-3">
            <h2 className="text-lg font-semibold">Attachments</h2>
            {(attachments ?? []).length > 0 ? (
              <div className="space-y-2">
                {(attachments ?? []).map((attachment) => (
                  <a
                    key={attachment.path}
                    href={api.challengeAttachmentUrl(comp, cat, name, attachment.path)}
                    className="flex items-center justify-between rounded border border-[var(--border)] px-3 py-2 text-sm hover:border-[var(--accent)]"
                  >
                    <span className="truncate">{attachment.path}</span>
                    <span className="ml-3 inline-flex items-center gap-1 text-[var(--muted)]">
                      <Download size={14} />
                      {formatBytes(attachment.size)}
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--muted)]">No attachments found in `src/`.</p>
            )}
          </div>

          <div className="card p-5 space-y-3">
            <h2 className="text-lg font-semibold">Run Exploit</h2>
            <button
              onClick={() => runExploit.mutate()}
              disabled={runExploit.isPending}
              className="btn-primary w-full disabled:opacity-50"
            >
              <span className="inline-flex items-center gap-2">
                <Play size={14} />
                {runExploit.isPending ? "Running..." : "Run `exploit.py`"}
              </span>
            </button>
            {runExploit.data && (
              <div className="space-y-2 text-sm">
                <p className="text-[var(--muted)]">Return code: {runExploit.data.returncode}</p>
                <pre className="overflow-auto rounded bg-black/40 p-3 whitespace-pre-wrap max-h-64">
                  {runExploit.data.stdout || runExploit.data.stderr || "(no output)"}
                </pre>
              </div>
            )}
            {runExploit.error && <p className="text-sm text-red-400">{String(runExploit.error)}</p>}
          </div>
        </aside>
      </section>
    </div>
  );
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function TabBtn({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px",
        active
          ? "border-[var(--accent)] text-[var(--accent)]"
          : "border-transparent text-[var(--muted)] hover:text-white"
      )}
    >
      {icon}
      {label}
    </button>
  );
}
