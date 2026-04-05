import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Check, X } from "lucide-react";
import { api } from "@/lib/api";

type SettingKey =
  | "basedir"
  | "terminal.cli_cmd"
  | "terminal.editor_cmd"
  | "terminal.wsl_distro"
  | "terminal.python_cmd"
  | "terminal.explorer_cmd"
  | "terminal.file_manager_cmd"
  | "serve.host"
  | "serve.port"
  | "auth.webui_cookie_name"
  | "auth.one_time_login_ttl_sec"
  | "auth.session_ttl_sec"
  | "anthropic_api_key"
  | "ai_model"
  | "ai_endpoint";

const GROUPS: { label: string; keys: SettingKey[] }[] = [
  {
    label: "Workspace",
    keys: ["basedir"],
  },
  {
    label: "Terminal",
    keys: [
      "terminal.cli_cmd",
      "terminal.editor_cmd",
      "terminal.wsl_distro",
      "terminal.python_cmd",
      "terminal.explorer_cmd",
      "terminal.file_manager_cmd",
    ],
  },
  {
    label: "Server",
    keys: ["serve.host", "serve.port"],
  },
  {
    label: "Auth",
    keys: ["auth.webui_cookie_name", "auth.one_time_login_ttl_sec", "auth.session_ttl_sec"],
  },
  {
    label: "AI",
    keys: ["anthropic_api_key", "ai_model", "ai_endpoint"],
  },
];

const KEY_LABEL: Record<SettingKey, string> = {
  basedir: "Base Directory",
  "terminal.cli_cmd": "Terminal Command",
  "terminal.editor_cmd": "Editor Command",
  "terminal.wsl_distro": "WSL Distribution",
  "terminal.python_cmd": "Python Command",
  "terminal.explorer_cmd": "Explorer Command",
  "terminal.file_manager_cmd": "File Manager Command",
  "serve.host": "Bind Host",
  "serve.port": "Bind Port",
  "auth.webui_cookie_name": "Cookie Name",
  "auth.one_time_login_ttl_sec": "One-Time Login TTL (s)",
  "auth.session_ttl_sec": "Session TTL (s)",
  anthropic_api_key: "Anthropic API Key",
  ai_model: "AI Model",
  ai_endpoint: "AI Endpoint",
};

function getByPath(obj: unknown, key: string): string {
  const value = key.split(".").reduce<unknown>((acc, part) => {
    if (acc && typeof acc === "object") {
      return (acc as Record<string, unknown>)[part];
    }
    return undefined;
  }, obj);
  if (value === null || value === undefined) return "";
  return String(value);
}

export default function Settings() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<SettingKey | null>(null);
  const [draft, setDraft] = useState("");
  const [savedKey, setSavedKey] = useState<SettingKey | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
  });

  const save = useMutation({
    mutationFn: async (key: SettingKey) => {
      const raw = draft;
      const parsed = /^-?\d+$/.test(raw) ? Number(raw) : raw;
      return api.patchConfig(key, parsed);
    },
    onSuccess: async (_, key) => {
      setSavedKey(key);
      setTimeout(() => setSavedKey(null), 2000);
      setEditing(null);
      await queryClient.invalidateQueries({ queryKey: ["config"] });
    },
  });

  const startEdit = (key: SettingKey) => {
    setDraft(getByPath(data, key));
    setEditing(key);
  };

  const cancelEdit = () => setEditing(null);

  const currentValue = useMemo(
    () => (key: SettingKey) => editing === key ? draft : getByPath(data, key),
    [data, editing, draft]
  );

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">Click the pencil icon to edit any setting. Enter to save, Escape to cancel.</p>
      </div>

      {isLoading && <p className="text-sm text-[var(--muted)]">Loading configuration...</p>}
      {error && <p className="text-sm text-red-400">{String(error)}</p>}

      {GROUPS.map((group) => (
        <section key={group.label} className="card p-5 space-y-1">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--muted)] mb-3">
            {group.label}
          </h2>
          {group.keys.map((key) => {
            const isEditing = editing === key;
            const value = currentValue(key);
            const isSaved = savedKey === key;
            const isSecret = key === "anthropic_api_key";

            return (
              <div
                key={key}
                className="group flex items-center gap-3 rounded px-2 py-2 hover:bg-white/5 transition-colors"
              >
                <div className="w-48 shrink-0">
                  <span className="text-sm text-[var(--muted)]">{KEY_LABEL[key]}</span>
                </div>

                <div className="flex-1 min-w-0">
                  {isEditing ? (
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") save.mutate(key);
                        if (e.key === "Escape") cancelEdit();
                      }}
                      className="w-full rounded border border-[var(--accent)] bg-black/20 px-2 py-1 text-sm outline-none"
                    />
                  ) : (
                    <span className="text-sm font-mono truncate block">
                      {isSecret && value ? "••••••••" : value || <span className="text-[var(--muted)] italic">not set</span>}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {isEditing ? (
                    <>
                      <button
                        onClick={() => save.mutate(key)}
                        disabled={save.isPending}
                        className="p-1 rounded text-green-400 hover:bg-green-400/10"
                        title="Save (Enter)"
                      >
                        <Check size={15} />
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="p-1 rounded text-[var(--muted)] hover:text-white hover:bg-white/10"
                        title="Cancel (Escape)"
                      >
                        <X size={15} />
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => startEdit(key)}
                      className="p-1 rounded text-[var(--muted)] opacity-0 group-hover:opacity-100 hover:text-white transition-opacity"
                      title="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                  )}
                  {isSaved && !isEditing && (
                    <span className="text-xs text-green-400 ml-1">Saved</span>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      ))}

      {save.error && <p className="text-sm text-red-400">{String(save.error)}</p>}
    </div>
  );
}
