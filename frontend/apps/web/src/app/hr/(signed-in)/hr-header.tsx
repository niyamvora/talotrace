"use client"

import { useRouter } from "next/navigation"
import { LogOutIcon } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"

import { useApi } from "@/hooks/use-api"
import { api, type HrUser } from "@/lib/api"

import { PROVIDERS } from "../login/providers"

// Also the sign-in gate: /api/hr/me answers 401 without the cookie, and api() then redirects to /hr/login.
export function HrHeader() {
  const router = useRouter()
  const { data: me } = useApi<HrUser>("/api/hr/me")

  async function signOut() {
    await api("/api/hr/logout", { method: "POST" })
    router.replace("/hr/login")
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <h1 className="font-heading text-lg font-semibold">HR review</h1>
        <Badge variant="outline">Mocked sign-in</Badge>
      </div>
      {me && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>
            {me.email} via {PROVIDERS[me.provider].name}
          </span>
          <Button variant="outline" size="sm" onClick={signOut}>
            <LogOutIcon data-icon="inline-start" />
            Sign out
          </Button>
        </div>
      )}
    </div>
  )
}
