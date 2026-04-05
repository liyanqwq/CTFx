export type ChallengeStatus = "fetched" | "seen" | "working" | "hoard" | "solved";

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

export type ConfigShape = {
  basedir?: string;
  active_competition?: string | null;
  terminal?: Record<string, unknown>;
  serve?: Record<string, unknown>;
  auth?: Record<string, unknown>;
  ai_model?: string | null;
  ai_endpoint?: string | null;
  anthropic_api_key?: string | null;
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
};
