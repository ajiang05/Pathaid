import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
export default function StudentLayout({children}:{children:React.ReactNode}) { return <Suspense fallback={<main className="center-state"><p>Loading PathAid…</p></main>}><AppShell>{children}</AppShell></Suspense>; }
