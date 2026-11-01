"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [["/home", "Home"], ["/discover", "Discover"], ["/profile", "Profile"]];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return <div className="app-frame">
    <aside className="sidebar">
      <Link className="brand" href="/home"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid<small>Local scholarship copilot</small></span></Link>
      <nav aria-label="Primary navigation">{links.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>{label}</Link>)}</nav>
      <div className="sidebar-footer"><Link href="/privacy">Privacy & safety</Link></div>
    </aside>
    <div className="app-content">
      <header className="mobile-header"><Link className="brand" href="/home"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid</span></Link></header>
      <main className="workspace">{children}</main>
      <nav className="mobile-nav" aria-label="Primary navigation">{links.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>{label}</Link>)}</nav>
    </div>
  </div>;
}
