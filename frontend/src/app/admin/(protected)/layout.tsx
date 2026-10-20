import {Suspense} from "react";import {AdminSessionProvider} from "@/components/admin-session";import {AdminShell} from "@/components/admin-shell";
export default function AdminLayout({children}:{children:React.ReactNode}){return <AdminSessionProvider><Suspense fallback={<main className="center-state">Loading…</main>}><AdminShell>{children}</AdminShell></Suspense></AdminSessionProvider>}
