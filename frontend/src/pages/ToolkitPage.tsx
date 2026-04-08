import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Upload,
  Wrench,
  X,
} from "lucide-react";
import { api, type ToolkitTool, type ToolkitSet } from "@/lib/api";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORIES = ["pwn", "crypto", "web", "forensics", "rev", "misc"];

function Badge({ label, color = "default" }: { label: string; color?: "default" | "green" | "purple" }) {
  return (
    <span
      className={cn(
        "px-1.5 py-0.5 rounded text-xs border",
        color === "green" && "border-green-500/40 text-green-400",
        color === "purple" && "border-purple-500/40 text-purple-300",
        color === "default" && "border-[var(--border)] text-[var(--muted)]"
      )}
    >
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Set Manager Panel
// ---------------------------------------------------------------------------

function SetManager({
  sets,
  onSetFilter,
  activeFilter,
}: {
  sets: ToolkitSet[];
  onSetFilter: (id: string | null) => void;
  activeFilter: string | null;
}) {
  const qc = useQueryClient();
  const [showImport, setShowImport] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importAlias, setImportAlias] = useState("");
  const [importError, setImportError] = useState("");

  const enableMut = useMutation({
    mutationFn: (id: string) => api.enableToolkitSet(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["toolkit-sets"] }),
  });

  const disableMut = useMutation({
    mutationFn: (id: string) => api.disableToolkitSet(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["toolkit-sets"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteToolkitSet(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["toolkit-sets"] }),
  });

  const importMut = useMutation({
    mutationFn: ({ url, alias }: { url: string; alias?: string }) =>
      api.importToolkitSet(url, alias || undefined),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["toolkit-sets"] });
      void qc.invalidateQueries({ queryKey: ["toolkit-tools"] });
      setShowImport(false);
      setImportUrl("");
      setImportAlias("");
      setImportError("");
    },
    onError: (e: Error) => setImportError(e.message),
  });

  function handleExport(setId: string) {
    api.exportToolkitSet(setId).then((data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${setId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }).catch(console.error);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider">Sets</h3>
        <button
          onClick={() => setShowImport((v) => !v)}
          className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
        >
          <Upload size={11} /> Import
        </button>
      </div>

      {showImport && (
        <div className="p-3 rounded border border-[var(--border)] bg-[var(--surface)] space-y-2 mb-3">
          <input
            className="input w-full text-sm"
            placeholder="URL (https://gist.github.com/...)"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
          />
          <input
            className="input w-full text-sm"
            placeholder="Alias (optional)"
            value={importAlias}
            onChange={(e) => setImportAlias(e.target.value)}
          />
          {importError && <p className="text-xs text-red-400">{importError}</p>}
          <div className="flex gap-2">
            <button
              className="btn btn-primary text-xs py-1 px-3"
              disabled={!importUrl.trim() || importMut.isPending}
              onClick={() =>
                importMut.mutate({ url: importUrl.trim(), alias: importAlias.trim() || undefined })
              }
            >
              {importMut.isPending ? "Importing…" : "Import"}
            </button>
            <button
              className="btn text-xs py-1 px-3"
              onClick={() => {
                setShowImport(false);
                setImportError("");
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* All tools filter */}
      <button
        onClick={() => onSetFilter(null)}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors",
          activeFilter === null
            ? "bg-[var(--accent)]/20 text-[var(--accent)]"
            : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]"
        )}
      >
        <Wrench size={13} />
        All active tools
      </button>

      {sets.map((s) => (
        <div
          key={s.id}
          className={cn(
            "group flex items-center gap-1.5 px-2 py-1.5 rounded text-sm transition-colors cursor-pointer",
            activeFilter === s.id
              ? "bg-[var(--accent)]/20 text-[var(--accent)]"
              : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]"
          )}
          onClick={() => onSetFilter(s.id)}
        >
          <span className="flex-1 truncate font-mono text-xs">{s.id}</span>
          <span className="text-xs opacity-60">{s.tool_count}</span>
          {s.active ? (
            <ToggleRight
              size={14}
              className="text-green-400 shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                if (!s.pinned) disableMut.mutate(s.id);
              }}
            />
          ) : (
            <ToggleLeft
              size={14}
              className="shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                enableMut.mutate(s.id);
              }}
            />
          )}
          <button
            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              handleExport(s.id);
            }}
            title="Export set"
          >
            <Download size={13} />
          </button>
          {!s.pinned && (
            <button
              className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-red-400 transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Delete set "${s.id}"?`)) deleteMut.mutate(s.id);
              }}
              title="Delete set"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tool Form (add / edit)
// ---------------------------------------------------------------------------

type ToolFormData = {
  id: string;
  name: string;
  cmd: string;
  categories: string[];
  tags: string;
  description: string;
  prompt: string;
  ref: string;
};

const EMPTY_FORM: ToolFormData = {
  id: "",
  name: "",
  cmd: "",
  categories: [],
  tags: "",
  description: "",
  prompt: "",
  ref: "",
};

function ToolForm({
  initial,
  sets,
  onSave,
  onCancel,
  isPending,
}: {
  initial?: ToolFormData & { setId?: string };
  sets: ToolkitSet[];
  onSave: (data: ToolFormData, setId: string) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [form, setForm] = useState<ToolFormData>(initial ?? EMPTY_FORM);
  const [targetSet, setTargetSet] = useState(initial?.setId ?? "personal");
  const isEdit = Boolean(initial?.id);

  function toggle(cat: string) {
    setForm((f) => ({
      ...f,
      categories: f.categories.includes(cat)
        ? f.categories.filter((c) => c !== cat)
        : [...f.categories, cat],
    }));
  }

  function field(k: keyof ToolFormData) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-[var(--muted)] mb-1">ID *</label>
          <input
            className="input w-full text-sm font-mono"
            placeholder="john-zip"
            value={form.id}
            onChange={field("id")}
            disabled={isEdit}
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--muted)] mb-1">Name *</label>
          <input className="input w-full text-sm" placeholder="John the Ripper (zip)" value={form.name} onChange={field("name")} />
        </div>
      </div>

      <div>
        <label className="block text-xs text-[var(--muted)] mb-1">Command template *</label>
        <input
          className="input w-full text-sm font-mono"
          placeholder="john --format=zip {file}"
          value={form.cmd}
          onChange={field("cmd")}
        />
        <p className="text-xs text-[var(--muted)] mt-1">Use {"{exploit}"}, {"{file}"}, {"{dir}"} as placeholders</p>
      </div>

      <div>
        <label className="block text-xs text-[var(--muted)] mb-1">Categories</label>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => toggle(c)}
              className={cn(
                "px-2 py-0.5 rounded text-xs border transition-colors",
                form.categories.includes(c)
                  ? "border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10"
                  : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)]"
              )}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs text-[var(--muted)] mb-1">Tags (comma-separated)</label>
        <input className="input w-full text-sm" placeholder="rop, x86_64, ret2libc" value={form.tags} onChange={field("tags")} />
      </div>

      <div>
        <label className="block text-xs text-[var(--muted)] mb-1">LLM prompt hint</label>
        <textarea
          className="input w-full text-sm resize-none"
          rows={2}
          placeholder="Use when binary has NX enabled and you need to leak libc. Check checksec first."
          value={form.prompt}
          onChange={field("prompt")}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-[var(--muted)] mb-1">Description</label>
          <input className="input w-full text-sm" value={form.description} onChange={field("description")} />
        </div>
        <div>
          <label className="block text-xs text-[var(--muted)] mb-1">Reference URL</label>
          <input className="input w-full text-sm" placeholder="https://..." value={form.ref} onChange={field("ref")} />
        </div>
      </div>

      {!isEdit && (
        <div>
          <label className="block text-xs text-[var(--muted)] mb-1">Add to set</label>
          <select
            className="input w-full text-sm"
            value={targetSet}
            onChange={(e) => setTargetSet(e.target.value)}
          >
            {sets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id}{s.pinned ? " (personal)" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          className="btn btn-primary text-sm"
          disabled={!form.id.trim() || !form.name.trim() || !form.cmd.trim() || isPending}
          onClick={() => onSave(form, targetSet)}
        >
          {isPending ? "Saving…" : isEdit ? "Save" : "Add Tool"}
        </button>
        <button className="btn text-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tool Card
// ---------------------------------------------------------------------------

function ToolCard({
  tool,
  onEdit,
  onDelete,
}: {
  tool: ToolkitTool;
  onEdit: (tool: ToolkitTool) => void;
  onDelete: (tool: ToolkitTool) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[var(--border)]/30 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? <ChevronDown size={13} className="shrink-0 text-[var(--muted)]" /> : <ChevronRight size={13} className="shrink-0 text-[var(--muted)]" />}
        <span className="font-mono text-sm font-semibold flex-1 truncate">{tool.id}</span>
        <span className="text-sm text-[var(--muted)] truncate hidden sm:block">{tool.name}</span>
        <div className="flex gap-1 flex-wrap justify-end">
          {tool.categories.map((c) => (
            <Badge key={c} label={c} color="green" />
          ))}
        </div>
        <span className="text-xs text-[var(--muted)] shrink-0">{tool._set}</span>
        <div className="flex gap-1 ml-1 shrink-0">
          <button
            className="p-1 text-[var(--muted)] hover:text-[var(--text)] transition-colors"
            onClick={(e) => { e.stopPropagation(); onEdit(tool); }}
            title="Edit"
          >
            <BookOpen size={13} />
          </button>
          <button
            className="p-1 text-[var(--muted)] hover:text-red-400 transition-colors"
            onClick={(e) => { e.stopPropagation(); onDelete(tool); }}
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-[var(--border)] space-y-2 text-sm">
          <div>
            <span className="text-[var(--muted)] text-xs">cmd</span>
            <pre className="mt-0.5 font-mono text-xs bg-black/20 px-3 py-2 rounded text-[var(--accent)] overflow-x-auto">
              {tool.cmd}
            </pre>
          </div>
          {tool.prompt && (
            <div>
              <span className="text-[var(--muted)] text-xs">LLM prompt</span>
              <p className="mt-0.5 text-sm italic text-[var(--text)] opacity-80">{tool.prompt}</p>
            </div>
          )}
          {tool.description && (
            <div>
              <span className="text-[var(--muted)] text-xs">description</span>
              <p className="mt-0.5 text-sm">{tool.description}</p>
            </div>
          )}
          {(tool.tags ?? []).length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {tool.tags.map((t) => <Badge key={t} label={t} color="purple" />)}
            </div>
          )}
          {tool.ref && (
            <a
              href={tool.ref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink size={11} /> {tool.ref}
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ToolkitPage() {
  const qc = useQueryClient();
  const [setFilter, setSetFilter] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editTool, setEditTool] = useState<ToolkitTool | null>(null);

  const { data: sets = [], isLoading: setsLoading } = useQuery({
    queryKey: ["toolkit-sets"],
    queryFn: () => api.listToolkitSets(),
  });

  const { data: tools = [], isLoading: toolsLoading } = useQuery({
    queryKey: ["toolkit-tools", setFilter, catFilter],
    queryFn: () =>
      api.listToolkitTools({
        set: setFilter ?? undefined,
        cat: catFilter ?? undefined,
      }),
  });

  const addMut = useMutation({
    mutationFn: ({ tool, setId }: { tool: Omit<ToolkitTool, "_set">; setId: string }) =>
      api.addToolkitTool(tool, setId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["toolkit-tools"] });
      void qc.invalidateQueries({ queryKey: ["toolkit-sets"] });
      setShowAddForm(false);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ tool, updates }: { tool: ToolkitTool; updates: Partial<Omit<ToolkitTool, "id" | "_set">> }) =>
      api.updateToolkitTool(tool.id, updates, tool._set),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["toolkit-tools"] });
      setEditTool(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (tool: ToolkitTool) => api.deleteToolkitTool(tool.id, tool._set),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["toolkit-tools"] });
      void qc.invalidateQueries({ queryKey: ["toolkit-sets"] });
    },
  });

  function handleSaveNew(data: ToolFormData, setId: string) {
    const tool: Omit<ToolkitTool, "_set"> = {
      id: data.id,
      name: data.name,
      cmd: data.cmd,
      categories: data.categories,
      tags: data.tags.split(",").map((t) => t.trim()).filter(Boolean),
      description: data.description,
      prompt: data.prompt,
      ref: data.ref || undefined,
    };
    addMut.mutate({ tool, setId });
  }

  function handleSaveEdit(data: ToolFormData, _setId: string) {
    if (!editTool) return;
    updateMut.mutate({
      tool: editTool,
      updates: {
        name: data.name,
        cmd: data.cmd,
        categories: data.categories,
        tags: data.tags.split(",").map((t) => t.trim()).filter(Boolean),
        description: data.description,
        prompt: data.prompt,
        ref: data.ref || undefined,
      },
    });
  }

  return (
    <div className="flex gap-6 h-full min-h-0">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 space-y-4">
        {setsLoading ? (
          <p className="text-xs text-[var(--muted)]">Loading…</p>
        ) : (
          <SetManager sets={sets} onSetFilter={setSetFilter} activeFilter={setFilter} />
        )}

        {/* Category filter */}
        <div>
          <h3 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-2">Category</h3>
          <button
            onClick={() => setCatFilter(null)}
            className={cn(
              "w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors",
              catFilter === null
                ? "bg-[var(--accent)]/20 text-[var(--accent)]"
                : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]"
            )}
          >
            All
          </button>
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCatFilter(c === catFilter ? null : c)}
              className={cn(
                "w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors",
                catFilter === c
                  ? "bg-[var(--accent)]/20 text-[var(--accent)]"
                  : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]"
              )}
            >
              {c}
            </button>
          ))}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">
            Toolkit
            {catFilter && <span className="ml-2 text-base font-normal text-[var(--muted)]">/ {catFilter}</span>}
            {setFilter && <span className="ml-2 text-base font-normal text-[var(--muted)]">/ {setFilter}</span>}
          </h1>
          <button
            className="btn btn-primary flex items-center gap-1.5 text-sm"
            onClick={() => { setShowAddForm(true); setEditTool(null); }}
          >
            <Plus size={14} /> Add Tool
          </button>
        </div>

        {/* Add form */}
        {showAddForm && !editTool && (
          <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm">New Tool</h2>
              <button onClick={() => setShowAddForm(false)}><X size={14} /></button>
            </div>
            <ToolForm
              sets={sets}
              onSave={handleSaveNew}
              onCancel={() => setShowAddForm(false)}
              isPending={addMut.isPending}
            />
            {addMut.error && (
              <p className="mt-2 text-xs text-red-400">{(addMut.error as Error).message}</p>
            )}
          </div>
        )}

        {/* Edit form */}
        {editTool && (
          <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm">Edit: {editTool.id}</h2>
              <button onClick={() => setEditTool(null)}><X size={14} /></button>
            </div>
            <ToolForm
              initial={{
                id: editTool.id,
                name: editTool.name,
                cmd: editTool.cmd,
                categories: editTool.categories,
                tags: (editTool.tags ?? []).join(", "),
                description: editTool.description ?? "",
                prompt: editTool.prompt ?? "",
                ref: editTool.ref ?? "",
                setId: editTool._set,
              }}
              sets={sets}
              onSave={handleSaveEdit}
              onCancel={() => setEditTool(null)}
              isPending={updateMut.isPending}
            />
            {updateMut.error && (
              <p className="mt-2 text-xs text-red-400">{(updateMut.error as Error).message}</p>
            )}
          </div>
        )}

        {/* Tool list */}
        {toolsLoading ? (
          <p className="text-sm text-[var(--muted)]">Loading tools…</p>
        ) : tools.length === 0 ? (
          <div className="text-center py-16 text-[var(--muted)]">
            <Wrench size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No tools found.</p>
            <p className="text-xs mt-1">Add a tool or import a set to get started.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {tools.map((tool) => (
              <ToolCard
                key={`${tool._set}:${tool.id}`}
                tool={tool}
                onEdit={(t) => { setEditTool(t); setShowAddForm(false); }}
                onDelete={(t) => {
                  if (confirm(`Remove tool "${t.id}" from set "${t._set}"?`)) {
                    deleteMut.mutate(t);
                  }
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
