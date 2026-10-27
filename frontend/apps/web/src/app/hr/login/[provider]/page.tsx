import { notFound } from "next/navigation"

import type { Provider } from "@/lib/api"

import { PROVIDERS } from "../providers"
import { MockProvider } from "./mock-provider"

export default async function Page({
  params,
}: {
  params: Promise<{ provider: string }>
}) {
  const { provider } = await params
  if (!Object.hasOwn(PROVIDERS, provider)) notFound()
  return <MockProvider provider={provider as Provider} />
}
