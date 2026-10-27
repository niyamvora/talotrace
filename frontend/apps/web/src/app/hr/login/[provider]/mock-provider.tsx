"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { CircleAlertIcon, MailIcon } from "lucide-react"

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Spinner } from "@workspace/ui/components/spinner"

import { api, errorMessage, type HrUser, type Provider } from "@/lib/api"

import { PROVIDERS } from "../providers"

// MOCK OAuth: looks like the provider's sign-in, but only asks for an email and the API accepts any
// well-formed one. No password is asked for, sent or stored.
export function MockProvider({ provider }: { provider: Provider }) {
  const { name, Logo } = PROVIDERS[provider]
  const router = useRouter()
  const [step, setStep] = useState<"email" | "consent" | "redirecting">(
    "email"
  )
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)

  async function allow() {
    setStep("redirecting")
    setError(null)
    try {
      await api<HrUser>("/api/hr/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, email }),
      })
      router.replace("/hr")
    } catch (e) {
      setError(errorMessage(e))
      setStep("consent")
    }
  }

  return (
    <Card className="mx-auto max-w-sm">
      <CardHeader className="items-center text-center">
        <Logo className="mx-auto mb-2 size-10" />
        {step === "email" ? (
          <>
            <CardTitle className="text-xl">Sign in with {name}</CardTitle>
            <CardDescription>to continue to TaloTrace</CardDescription>
          </>
        ) : (
          <>
            <CardTitle className="text-xl">
              TaloTrace wants to access your {name} account
            </CardTitle>
            <CardDescription className="flex justify-center">
              <Badge variant="outline">
                <MailIcon data-icon="inline-start" />
                {email}
              </Badge>
            </CardDescription>
          </>
        )}
      </CardHeader>

      {step === "email" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setStep("consent")
          }}
          className="contents"
        >
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <FieldDescription>
                  MOCK: any email works. No password, and nothing is sent to{" "}
                  {name}.
                </FieldDescription>
              </Field>
            </FieldGroup>
          </CardContent>
          <CardFooter className="justify-between">
            <Button
              variant="ghost"
              render={<Link href="/hr/login" />}
              nativeButton={false}
            >
              Cancel
            </Button>
            <Button type="submit">Next</Button>
          </CardFooter>
        </form>
      ) : (
        <>
          <CardContent className="flex flex-col gap-3">
            <p className="text-muted-foreground">
              This will allow TaloTrace to see your email address, which is
              recorded on any score you override.
            </p>
            {error && (
              <Alert variant="destructive">
                <CircleAlertIcon />
                <AlertTitle>Sign-in failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
          <CardFooter className="justify-between">
            <Button
              variant="ghost"
              disabled={step === "redirecting"}
              onClick={() => setStep("email")}
            >
              Back
            </Button>
            <Button onClick={allow} disabled={step === "redirecting"}>
              {step === "redirecting" && <Spinner data-icon="inline-start" />}
              {step === "redirecting" ? "Redirecting…" : "Allow"}
            </Button>
          </CardFooter>
        </>
      )}
    </Card>
  )
}
