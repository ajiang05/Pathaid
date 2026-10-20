import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "PathAid", template: "%s | PathAid" },
  description: "Find reviewed scholarships and student support with clear, source-backed eligibility guidance.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="en"><body>{children}</body></html>;
}
