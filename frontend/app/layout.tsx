import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Football Analytics - Match Prediction",
  description: "Real data match prediction, radar and what-if simulator",
  manifest: "/manifest.json",
  themeColor: "#0f172a",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Football Analytics" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#0f172a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="format-detection" content="telephone=no" />
      </head>
      <body className="bg-[#0f172a] text-white antialiased min-h-screen" style={{ WebkitTapHighlightColor: "transparent" }}>
        {children}
      </body>
    </html>
  );
}
