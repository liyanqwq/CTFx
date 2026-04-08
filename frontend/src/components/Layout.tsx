import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Flag, Settings, Swords, Table2, Terminal, Trophy, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { useComp } from "@/lib/compContext";
import { cn } from "@/lib/utils";

export default function Layout() {
  const { comp, setComp } = useComp();
  const navigate = useNavigate();
  const location = useLocation();

  const hasComp = comp !== "unknown";
  const onCompetitionsPage = location.pathname.startsWith("/competitions");

  const { data: info } = useQuery({
    queryKey: ["info", comp],
    queryFn: () => api.getInfo(comp),
    enabled: hasComp,
  });

  const { data: competitions } = useQuery({
    queryKey: ["competitions"],
    queryFn: () => api.listCompetitions(),
    staleTime: 30_000,
  });

  const [selectorOpen, setSelectorOpen] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (selectorRef.current && !selectorRef.current.contains(e.target as Node)) {
        setSelectorOpen(false);
      }
    }

    if (selectorOpen) {
      document.addEventListener("mousedown", onClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", onClickOutside);
    };
  }, [selectorOpen]);

  const solved = useMemo(() => {
    if (!info?.challenges) return null;
    return Object.values(info.challenges).filter((c) => c.status === "solved").length;
  }, [info]);

  const total = info ? Object.keys(info.challenges ?? {}).length : null;
  const isAwd = info?.mode === "awd";

  function switchComp(dir: string) {
    setComp(dir);
    setSelectorOpen(false);
    void api.setActiveCompetition(dir).catch(() => undefined);
    navigate("/");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2 flex items-center gap-4">
        <span className="font-bold text-[var(--accent)] tracking-wide text-lg flex items-center gap-2">
          <Terminal size={18} />
          CTFx
        </span>

        <div className="relative" ref={selectorRef}>
          <button
            onClick={() => setSelectorOpen((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] transition-colors px-2 py-1 rounded hover:bg-[var(--border)]"
          >
            {info ? (
              <>
                <span>
                  {info.name} {info.year}
                </span>
                <span className="px-1.5 py-0.5 rounded text-xs border border-[var(--border)]">
                  {info.mode}
                </span>
              </>
            ) : (
              <span className="italic">{hasComp ? comp : "No competition selected"}</span>
            )}
            <ChevronDown size={13} className={cn("transition-transform", selectorOpen && "rotate-180")} />
          </button>

          {selectorOpen && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-[var(--surface)] border border-[var(--border)] rounded shadow-lg min-w-56 max-h-72 overflow-y-auto">
              {competitions && competitions.length > 0 ? (
                competitions.map((c) => (
                  <button
                    key={c.dir}
                    onClick={() => switchComp(c.dir)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--border)] transition-colors text-left"
                  >
                    <Check
                      size={13}
                      className={cn("shrink-0", c.dir === comp ? "text-[var(--accent)]" : "opacity-0")}
                    />
                    <span className="flex-1 truncate">
                      {c.name} {c.year}
                    </span>
                    <span className="text-xs text-[var(--muted)] shrink-0">
                      {c.solved}/{c.total}
                    </span>
                  </button>
                ))
              ) : (
                <p className="px-3 py-2 text-sm text-[var(--muted)]">No competitions found</p>
              )}

              <div className="border-t border-[var(--border)] mt-1 pt-1 pb-1">
                <button
                  onClick={() => {
                    setSelectorOpen(false);
                    navigate("/competitions");
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--accent)] hover:bg-[var(--border)] transition-colors text-left"
                >
                  <Trophy size={13} />
                  Manage competitions
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="ml-auto flex gap-1">
          {solved !== null && (
            <span className="text-xs text-[var(--muted)]">
              {solved}/{total} solved
            </span>
          )}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <nav className="w-44 shrink-0 border-r border-[var(--border)] bg-[var(--surface)] p-3 flex flex-col gap-1">
          <NavItem to="/" icon={<Terminal size={14} />} label="Dashboard" />
          <NavItem to="/flags" icon={<Table2 size={14} />} label="Flags" />
          <NavItem to="/submit" icon={<Flag size={14} />} label="Submit Flag" />
          <NavItem to="/toolkit" icon={<Wrench size={14} />} label="Toolkit" />
          {isAwd && (
            <>
              <div className="mt-3 mb-1 px-2 text-xs text-[var(--muted)] uppercase tracking-wider">AWD</div>
              <NavItem to="/awd" icon={<Swords size={14} />} label="Services" />
            </>
          )}
          <div className="mt-auto pt-3 border-t border-[var(--border)] flex flex-col gap-1">
            <NavItem to="/competitions" icon={<Trophy size={14} />} label="Competitions" />
            <NavItem to="/settings" icon={<Settings size={14} />} label="Settings" />
          </div>
        </nav>

        <main className="flex-1 overflow-auto p-6">
          {!hasComp && !onCompetitionsPage ? <NoCompLanding /> : <Outlet context={{ comp, info }} />}
        </main>
      </div>

      <footer className="border-t border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-center text-xs text-[var(--muted)]">
        Powered by{" "}
        <a
          href="https://github.com/liyanqwq/CTFx"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--accent)] hover:underline"
        >
          CTFx
        </a>{" "}
        by{" "}
        <a
          href="//liyan.moe"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--text)] hover:text-[var(--accent)] transition-colors"
        >
          Li Yan
        </a>
      </footer>
    </div>
  );
}

function NoCompLanding() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-64 text-center space-y-4">
      <Trophy size={48} className="text-[var(--accent)] opacity-40" />
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">No competition selected</h2>
        <p className="text-sm text-[var(--muted)]">
          Select an existing competition or create a new one to get started.
        </p>
      </div>
      <Link to="/competitions" className="btn btn-primary text-sm">
        Browse Competitions
      </Link>
    </div>
  );
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors",
          isActive
            ? "bg-[var(--accent)]/20 text-[var(--accent)]"
            : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--border)]"
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}
