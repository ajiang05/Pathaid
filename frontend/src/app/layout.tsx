import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "PathAid", template: "%s | PathAid" },
  description: "A private local scholarship finder and application copilot.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="en" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
