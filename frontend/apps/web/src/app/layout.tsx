import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import Link from "next/link"

import "@workspace/ui/globals.css"
import { ModeToggle } from "@/components/mode-toggle"
import { ThemeProvider } from "@/components/theme-provider"
import { cn } from "@workspace/ui/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'})

const fontMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export const metadata: Metadata = {
  title: "TaloTrace",
  description: "AI suggests a score, HR decides.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn("antialiased", fontMono.variable, "font-sans", geist.variable)}
    >
      {/* ponytail: extensions (e.g. ColorZilla's cz-shortcut-listen) inject body attrs pre-hydration */}
      <body suppressHydrationWarning>
        <ThemeProvider>
          <header className="border-b">
            <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
              <Link href="/" className="font-heading font-semibold">
                TaloTrace
              </Link>
              <ModeToggle />
            </div>
          </header>
          <main className="mx-auto w-full max-w-5xl px-4 py-8">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  )
}
