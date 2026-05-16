import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Indies — Transparencia en compras públicas",
  description:
    "Consulta órdenes de compra del Estado chileno en lenguaje natural.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
