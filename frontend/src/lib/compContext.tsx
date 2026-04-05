import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type CompContextValue = {
  comp: string;
  setComp: (value: string) => void;
};

const CompContext = createContext<CompContextValue | null>(null);

const STORAGE_KEY = "ctfx.activeCompetition";

export function CompProvider({ children }: { children: React.ReactNode }) {
  const [comp, setCompState] = useState<string>(() => localStorage.getItem(STORAGE_KEY) ?? "unknown");

  // On mount, sync with server config.json — server is authoritative.
  // This ensures a fresh browser (or cleared localStorage) still picks up
  // whatever active_competition was last set via the CLI.
  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        const serverComp = cfg.active_competition;
        if (serverComp) {
          localStorage.setItem(STORAGE_KEY, serverComp);
          setCompState(serverComp);
        }
      })
      .catch(() => undefined);
  }, []); // intentionally run once on mount only

  const value = useMemo<CompContextValue>(
    () => ({
      comp,
      setComp: (next: string) => {
        localStorage.setItem(STORAGE_KEY, next);
        setCompState(next);
      },
    }),
    [comp]
  );

  return <CompContext.Provider value={value}>{children}</CompContext.Provider>;
}

export function useComp() {
  const ctx = useContext(CompContext);
  if (!ctx) {
    throw new Error("useComp must be used within CompProvider");
  }
  return ctx;
}
