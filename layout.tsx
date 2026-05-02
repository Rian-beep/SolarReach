import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SolarReach",
  description: "AI-powered solar outreach platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">{children}</body>
    </html>
  );
}
