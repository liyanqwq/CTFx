export type ChallengeStatus = "fetched" | "seen" | "working" | "hoard" | "solved";

export type ToolkitTool = {
  id: string;
  name: string;
  cmd: string;
  categories: string[];
  tags: string[];
  description?: string;
  prompt?: string;
  ref?: string | null;
  _set?: string;
};

export type ToolkitSet = {
  id: string;
  active: boolean;
  pinned: boolean;
  source?: string | null;
  tool_count: number;
};

export type CompetitionSummary = {
  dir: string;
  name: string;
  year: number;
  mode: string;
  platform?: string;
  solved: number;
  total: number;
};

export type ChallengeRecord = {
  name: string;
  category: string;
  status: ChallengeStatus;
  points?: number;
  remote?: string;
  description?: string;
  flag?: string | null;
  path?: string;
  extra_info?: string | null;
  attachments?: AttachmentRecord[];
};

export type AttachmentRecord = {
  name: string;
  path: string;
  size: number;
};

export type CompetitionInfo = {
  name: string;
  year: number;
  mode: string;
  platform?: string;
  url?: string | null;
  flag_format?: string | null;
  team_name?: string | null;
  team_token?: string | null;
  team_cookies?: string | null;
  submit_api?: boolean;
  challenges: Record<string, Partial<ChallengeRecord>>;
  services?: Record<string, unknown>;
};

export type RemoteChallengeRecord = {
  platform_id: number;
  name: string;
  display_name: string;
  category: string;
  description?: string;
  points?: number | null;
  connection_info?: string;
  files?: string[];
  solved_by_me?: boolean;
};

export type PlatformStatus = {
  base_url: string;
  auth_mode: string;
  authenticated: boolean;
  challenge_count: number;
  solved_count: number;
  scoreboard_entries: number;
};

export type PlatformScoreboardEntry = {
  name?: string;
  account_name?: string;
  team?: string;
  score?: number;
  value?: number;
};

export type PlatformSolveEntry = {
  date?: string;
  created?: string;
  name?: string;
  account_name?: string;
  user?: string;
};

export type ConfigShape = {
  basedir?: string;
  active_competition?: string | null;
  terminal?: Record<string, unknown>;
  serve?: Record<string, unknown>;
  auth?: Record<string, unknown>;
  ai_provider?: string | null;
  ai_model?: string | null;
  ai_api_key?: string | null;
  ai_openai_base_url?: string | null;
  ai_anthropic_base_url?: string | null;
  ai_endpoint?: string | null;
  anthropic_api_key?: string | null;
};

export type AiTestResult = {
  ok: boolean;
  provider: string;
  model: string;
  base_url: string;
  text: string;
};

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      const text = await res.text();
      if (text) {
        detail = text;
      }
    }
    throw new Error(detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

async function requestText(path: string, init?: RequestInit): Promise<string> {
  const res = await fetch(path, {
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.text();
}

function normalizeChallenge(key: string, value: Partial<ChallengeRecord>): ChallengeRecord {
  const [category = "misc", name = key] = key.split("/");
  return {
    name,
    category,
    status: (value.status as ChallengeStatus) ?? "fetched",
    points: value.points,
    remote: value.remote,
    description: value.description,
    flag: value.flag ?? null,
    path: value.path,
    extra_info: value.extra_info ?? null,
  };
}

export const api = {
  getConfig() {
    return request<ConfigShape>("/api/config");
  },

  patchConfig(key: string, value: JsonValue) {
    return request<{ ok: boolean; key: string; value: JsonValue }>("/api/config", {
      method: "PATCH",
      body: JSON.stringify({ key, value }),
    });
  },

  aiTest() {
    return request<AiTestResult>("/api/config/ai-test", {
      method: "POST",
    });
  },

  listCompetitions() {
    return request<CompetitionSummary[]>("/api/competitions");
  },

  createCompetition(body: {
    name: string;
    year: number;
    mode: string;
    platform: string;
    url?: string;
    flag_format?: string;
    team_name?: string;
    team_token?: string;
  }) {
    return request<CompetitionSummary>("/api/competitions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  setActiveCompetition(competition: string) {
    return request<{ active_competition: string }>("/api/competitions/active", {
      method: "PUT",
      body: JSON.stringify({ competition }),
    });
  },

  getInfo(comp: string) {
    return request<CompetitionInfo>(`/api/${encodeURIComponent(comp)}/info`);
  },

  updateCompetition(
    comp: string,
    body: Partial<
      Pick<
        CompetitionInfo,
        "name" | "year" | "mode" | "platform" | "url" | "flag_format" | "team_name" | "team_token" | "team_cookies" | "submit_api"
      >
    >
  ) {
    return request<CompetitionInfo>(`/api/${encodeURIComponent(comp)}/info`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  async listChallenges(comp: string) {
    return request<ChallengeRecord[]>(`/api/${encodeURIComponent(comp)}/challenges`);
  },

  async getChallenge(comp: string, cat: string, name: string) {
    return request<ChallengeRecord>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}`
    );
  },

  async getChallengeMap(comp: string) {
    const info = await api.getInfo(comp);
    return Object.entries(info.challenges ?? {}).map(([key, value]) => normalizeChallenge(key, value));
  },

  updateChallengeStatus(comp: string, cat: string, name: string, status: ChallengeStatus, flag?: string) {
    return request<{ ok: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/status`,
      {
        method: "POST",
        body: JSON.stringify({ status, flag }),
      }
    );
  },

  updateChallengeMeta(
    comp: string,
    cat: string,
    name: string,
    body: { points?: number | null; remote?: string | null; extra_info?: string | null }
  ) {
    return request<ChallengeRecord>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/meta`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      }
    );
  },

  recordFlag(comp: string, cat: string, name: string, flag: string) {
    return request<{ ok: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/flag`,
      {
        method: "POST",
        body: JSON.stringify({ flag }),
      }
    );
  },

  submitFlag(comp: string, cat: string, name: string, flag: string) {
    return request<Record<string, unknown>>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/submit`,
      {
        method: "POST",
        body: JSON.stringify({ flag }),
      }
    );
  },

  addChallenge(
    comp: string,
    body: { name: string; category: string; description?: string; points?: number; remote?: string }
  ) {
    return request<ChallengeRecord>(`/api/${encodeURIComponent(comp)}/challenges`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deleteChallenge(comp: string, cat: string, name: string) {
    return request<{ ok: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}`,
      {
        method: "DELETE",
      }
    );
  },

  fetchChallenges(comp: string, cat?: string, chal?: string) {
    const params = new URLSearchParams();
    if (cat) params.set("cat", cat);
    if (chal) params.set("chal", chal);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<{ created: string }>(`/api/${encodeURIComponent(comp)}/fetch${suffix}`, {
      method: "POST",
    });
  },

  runExploit(comp: string, cat: string, name: string) {
    return request<{ stdout: string; stderr: string; returncode: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/run`,
      { method: "POST" }
    );
  },

  listAwdExploits(comp: string, service: string) {
    return request<Array<Record<string, unknown>>>(
      `/api/${encodeURIComponent(comp)}/awd/exploits/${encodeURIComponent(service)}`
    );
  },

  listAwdPatches(comp: string, service: string) {
    return request<Array<Record<string, unknown>>>(
      `/api/${encodeURIComponent(comp)}/awd/patches/${encodeURIComponent(service)}`
    );
  },

  listAwdHosts(comp: string, service: string) {
    return request<Array<{ team: string; ip: string }>>(
      `/api/${encodeURIComponent(comp)}/awd/hosts/${encodeURIComponent(service)}`
    );
  },

  getChalMd(comp: string, cat: string, name: string) {
    return requestText(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/chal.md`
    );
  },

  putChalMd(comp: string, cat: string, name: string, content: string) {
    return request<{ ok: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/chal.md`,
      {
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: content,
      }
    );
  },

  getWpMd(comp: string, cat: string, name: string) {
    return requestText(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/wp.md`
    );
  },

  putWpMd(comp: string, cat: string, name: string, content: string) {
    return request<{ ok: string }>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/wp.md`,
      {
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: content,
      }
    );
  },

  // Toolkit
  listToolkitSets() {
    return request<ToolkitSet[]>("/api/toolkit/sets");
  },

  createToolkitSet(id: string, name: string) {
    return request<{ id: string; name: string }>("/api/toolkit/sets", {
      method: "POST",
      body: JSON.stringify({ id, name }),
    });
  },

  deleteToolkitSet(setId: string) {
    return request<{ ok: boolean }>(`/api/toolkit/sets/${encodeURIComponent(setId)}`, {
      method: "DELETE",
    });
  },

  enableToolkitSet(setId: string) {
    return request<{ ok: boolean }>(`/api/toolkit/sets/${encodeURIComponent(setId)}/enable`, {
      method: "POST",
    });
  },

  disableToolkitSet(setId: string) {
    return request<{ ok: boolean }>(`/api/toolkit/sets/${encodeURIComponent(setId)}/disable`, {
      method: "POST",
    });
  },

  importToolkitSet(url: string, alias?: string) {
    return request<{ id: string }>("/api/toolkit/import", {
      method: "POST",
      body: JSON.stringify({ url, alias: alias || undefined }),
    });
  },

  exportToolkitSet(setId: string) {
    return request<Record<string, unknown>>(`/api/toolkit/export/${encodeURIComponent(setId)}`);
  },

  listToolkitTools(params?: { cat?: string; tag?: string; set?: string }) {
    const q = new URLSearchParams();
    if (params?.cat) q.set("cat", params.cat);
    if (params?.tag) q.set("tag", params.tag);
    if (params?.set) q.set("set", params.set);
    const suffix = q.toString() ? `?${q.toString()}` : "";
    return request<ToolkitTool[]>(`/api/toolkit/tools${suffix}`);
  },

  addToolkitTool(tool: Omit<ToolkitTool, "_set">, setId = "personal") {
    return request<ToolkitTool>(`/api/toolkit/tools?set_id=${encodeURIComponent(setId)}`, {
      method: "POST",
      body: JSON.stringify(tool),
    });
  },

  updateToolkitTool(toolId: string, updates: Partial<Omit<ToolkitTool, "id" | "_set">>, setId?: string) {
    const suffix = setId ? `?set_id=${encodeURIComponent(setId)}` : "";
    return request<ToolkitTool>(`/api/toolkit/tools/${encodeURIComponent(toolId)}${suffix}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  deleteToolkitTool(toolId: string, setId?: string) {
    const suffix = setId ? `?set_id=${encodeURIComponent(setId)}` : "";
    return request<{ ok: boolean; set: string }>(
      `/api/toolkit/tools/${encodeURIComponent(toolId)}${suffix}`,
      { method: "DELETE" }
    );
  },

  listChallengeAttachments(comp: string, cat: string, name: string) {
    return request<AttachmentRecord[]>(
      `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/attachments`
    );
  },

  challengeAttachmentUrl(comp: string, cat: string, name: string, attachmentPath: string) {
    return `/api/${encodeURIComponent(comp)}/challenges/${encodeURIComponent(cat)}/${encodeURIComponent(name)}/attachments/${attachmentPath
      .split("/")
      .map((part) => encodeURIComponent(part))
      .join("/")}`;
  },

  getPlatformStatus(comp: string) {
    return request<PlatformStatus>(`/api/${encodeURIComponent(comp)}/platform/status`);
  },

  listPlatformChallenges(comp: string) {
    return request<RemoteChallengeRecord[]>(`/api/${encodeURIComponent(comp)}/platform/challenges`);
  },

  getPlatformScoreboard(comp: string) {
    return request<PlatformScoreboardEntry[]>(`/api/${encodeURIComponent(comp)}/platform/scoreboard`);
  },

  getPlatformChallengeSolves(comp: string, challengeId: number) {
    return request<PlatformSolveEntry[]>(
      `/api/${encodeURIComponent(comp)}/platform/challenges/${challengeId}/solves`
    );
  },
};
