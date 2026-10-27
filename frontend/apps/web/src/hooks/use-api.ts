"use client"

import { useCallback, useEffect, useState } from "react"

import { api } from "@/lib/api"

// GET `path` on mount; while `pollWhile(data)` is true, re-fetch every 5 s. Old data stays on screen if a refetch fails.
export function useApi<T>(path: string, pollWhile?: (data: T) => boolean) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(async () => {
    try {
      setData(await api<T>(path))
      setError(null)
    } catch (e) {
      setError(e)
    }
  }, [path])

  useEffect(() => {
    load()
  }, [load])

  const polling = data !== null && !!pollWhile?.(data)
  useEffect(() => {
    if (!polling) return
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [polling, load])

  return { data, error, load, polling }
}
