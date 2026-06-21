import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scanix AI | Elite Label Intelligence",
  description: "Decode your food at the molecular level with enterprise-grade label intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-scanix-ivory text-scanix-slate min-h-screen">
        {children}
      </body>
    </html>
  );
}