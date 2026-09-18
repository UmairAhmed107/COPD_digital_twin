import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "COPD Digital Twin | Interactive Clinical Simulation & State Tracking",
  description:
    "Interactive COPD Digital Twin demonstration featuring single FEV1 prediction, evolving longitudinal patient state tracking, and what-if clinical intervention trajectory simulations.",
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
