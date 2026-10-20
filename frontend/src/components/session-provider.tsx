"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";

type Session = { status:"loading"|"authenticated"|"anonymous"|"unavailable"; csrf:string|null; refresh:()=>Promise<void>; logout:()=>Promise<void> };
const SessionContext = createContext<Session|null>(null);

export function SessionProvider({ children }:{children:React.ReactNode}) {
  const [status,setStatus] = useState<Session["status"]>("loading");
  const [csrf,setCsrf] = useState<string|null>(null);
  const refresh = useCallback(async () => {
    setStatus("loading");
    try {
      const result = await api<{csrf_token:string}>("/api/auth/session");
      setCsrf(result.csrf_token); setStatus("authenticated");
    } catch (error) {
      setCsrf(null); setStatus(error instanceof ApiError && error.status===401 ? "anonymous" : "unavailable");
    }
  },[]);
  const logout = useCallback(async () => {
    if (csrf) await api<void>("/api/auth/logout", {method:"POST",headers:{"X-CSRF-Token":csrf}});
    setCsrf(null); setStatus("anonymous");
  },[csrf]);
  useEffect(() => { const timer=window.setTimeout(()=>void refresh(),0); return()=>window.clearTimeout(timer); },[refresh]);
  const value = useMemo(() => ({status,csrf,refresh,logout}),[status,csrf,refresh,logout]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
