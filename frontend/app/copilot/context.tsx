"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type CopilotLaunch = {
  plan?: number;
  document?: number;
  note?: number;
  prototype?: number;
  epic?: string;
  notes?: string;
  prompt?: string;
};

type CopilotState = {
  opened: boolean;
  launch: CopilotLaunch | null;
  open: (next?: CopilotLaunch) => void;
  close: () => void;
};

const CopilotContext = createContext<CopilotState>({
  opened: false,
  launch: null,
  open: () => undefined,
  close: () => undefined,
});

function hasLaunch(next?: CopilotLaunch) {
  return Boolean(next?.plan || next?.document || next?.note || next?.prototype || next?.epic || next?.notes || next?.prompt);
}

export function CopilotProvider({ children }: { children: ReactNode }) {
  const [opened, setOpened] = useState(false);
  const [launch, setLaunch] = useState<CopilotLaunch | null>(null);
  const open = useCallback((next?: CopilotLaunch) => {
    setLaunch(hasLaunch(next) ? { ...next } : null);
    setOpened(true);
  }, []);
  const close = useCallback(() => setOpened(false), []);
  const value = useMemo(() => ({ opened, launch, open, close }), [opened, launch, open, close]);
  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}

export function useCopilot() {
  return useContext(CopilotContext);
}
