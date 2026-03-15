import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { BaymaxProvider } from "@/components/BaymaxContext";
import { BaymaxAvatar } from "@/components/BaymaxAvatar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Amazon Research Tool",
  description: "AI-powered product research with review analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <BaymaxProvider>
          {children}
          <BaymaxAvatar />
        </BaymaxProvider>
      </body>
    </html>
  );
}
