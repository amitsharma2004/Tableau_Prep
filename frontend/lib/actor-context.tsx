"use client";

import { createContext, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "tableau-ai-prep:actor-email";
const DEFAULT_ACTOR = "shubhanshu@tnqtech.com";

interface ActorContextValue {
  actorEmail: string;
  setActorEmail: (email: string) => void;
}

const ActorContext = createContext<ActorContextValue | null>(null);

export function ActorProvider({ children }: { children: React.ReactNode }) {
  const [actorEmail, setActorEmailState] = useState(DEFAULT_ACTOR);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      // One-time hydration from localStorage on mount, not a reaction to
      // changing props/state - the intentional exception to this rule.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (stored) setActorEmailState(stored);
    } catch {
      // localStorage unavailable (private mode etc.) - fall back to default
    }
  }, []);

  const setActorEmail = (email: string) => {
    setActorEmailState(email);
    try {
      localStorage.setItem(STORAGE_KEY, email);
    } catch {
      // ignore - per-viewer convenience only
    }
  };

  return <ActorContext.Provider value={{ actorEmail, setActorEmail }}>{children}</ActorContext.Provider>;
}

export function useActor(): ActorContextValue {
  const ctx = useContext(ActorContext);
  if (!ctx) throw new Error("useActor must be used within an ActorProvider");
  return ctx;
}
