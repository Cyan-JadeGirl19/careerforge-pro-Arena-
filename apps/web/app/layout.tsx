import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerForge Pro",
  description:
    "CV-first career acceleration for South African professionals pursuing remote work globally.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
