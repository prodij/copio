import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Copio",
  description: "Diagnostic agent for Amazon-native CEOs.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
