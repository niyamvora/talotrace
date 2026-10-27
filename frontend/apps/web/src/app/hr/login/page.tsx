import Link from "next/link"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"

import type { Provider } from "@/lib/api"

import { PROVIDERS } from "./providers"

export default function Page() {
  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader>
        <CardTitle>Sign in to HR review</CardTitle>
        <CardDescription>See every answer and its suggested score.</CardDescription>
        <CardAction>
          <Badge variant="outline">Mocked sign-in</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {(Object.keys(PROVIDERS) as Provider[]).map((id) => {
          const { name, Logo } = PROVIDERS[id]
          return (
            <Button
              key={id}
              variant="outline"
              size="lg"
              render={<Link href={`/hr/login/${id}`} />}
              nativeButton={false}
            >
              <Logo data-icon="inline-start" />
              Continue with {name}
            </Button>
          )
        })}
      </CardContent>
      <CardFooter>
        <p className="text-xs text-muted-foreground">
          MOCK: no real Google or Facebook account is used, and no password is
          asked for or stored.
        </p>
      </CardFooter>
    </Card>
  )
}
