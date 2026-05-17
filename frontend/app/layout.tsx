import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VigIA — Datos públicos de Chile",
  description:
    "Mercado Público, Contraloría y Congreso en Chile. Pregunta en lenguaje natural.",
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png", sizes: "512x456" }],
    shortcut: "/favicon.png",
    apple: "/favicon.png",
  },
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
