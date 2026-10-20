import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/session-provider";

export const metadata: Metadata = {
  title: { default: "PathAid", template: "%s | PathAid" },
  description: "Find reviewed scholarships and student support with clear, source-backed eligibility guidance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="en" data-scroll-behavior="smooth"><body><SessionProvider>{children}</SessionProvider></body></html>;
}
