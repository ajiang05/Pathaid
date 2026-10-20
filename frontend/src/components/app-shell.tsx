"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";

const links = [["/home","Overview"],["/discover","Discover"],["/profile","Student profile"]];

export function AppShell({children}:{children:React.ReactNode}) {
  const pathname=usePathname(); const router=useRouter(); const session=useSession();
  if (session.status==="loading") return <main className="center-state" aria-live="polite"><p className="eyebrow">Loading your account</p><h1>Preparing PathAid…</h1></main>;
  if (session.status==="anonymous") return <main className="center-state"><p className="eyebrow">Session expired</p><h1>Log in to continue.</h1><Link className="button button-primary" href="/login">Log in</Link></main>;
  if (session.status==="unavailable") return <main className="center-state"><p className="eyebrow">Service unavailable</p><h1>We cannot load your account.</h1><button className="button button-primary" onClick={()=>void session.refresh()}>Try again</button></main>;
  async function signOut(){ await session.logout(); router.push("/login"); router.refresh(); }
  return <div className="app-frame">
    <aside className="sidebar">
      <Link className="brand" href="/home"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid<small>Student support</small></span></Link>
      <nav aria-label="Student navigation">{links.map(([href,label])=><Link key={href} href={href} aria-current={pathname===href?"page":undefined}>{label}</Link>)}</nav>
      <div className="sidebar-footer"><Link href="/privacy">Help & privacy</Link><button onClick={()=>void signOut()}>Log out</button></div>
    </aside>
    <div className="app-content">
      <header className="mobile-header"><Link className="brand" href="/home"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid</span></Link></header>
      <main className="workspace">{children}</main>
      <nav className="mobile-nav" aria-label="Student navigation">{links.map(([href,label])=><Link key={href} href={href} aria-current={pathname===href?"page":undefined}>{label}</Link>)}</nav>
    </div>
  </div>;
}
