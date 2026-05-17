import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TransparencIA — Datos públicos de Chile",
  description:
    "Mercado Público, Contraloría y Congreso en Chile. Pregunta en lenguaje natural.",
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
