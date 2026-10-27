"use client"

import Link from "next/link"
import { BriefcaseIcon } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import { LoadError } from "@/components/load-error"
import { StatusCounts } from "@/components/status-badge"
import { useApi } from "@/hooks/use-api"
import type { RoleSummary } from "@/lib/api"

export default function Page() {
  const { data: roles, error, load } = useApi<RoleSummary[]>(
    "/api/hr/roles",
    (rs) => rs.some((r) => r.counts.queued + r.counts.running > 0)
  )

  if (!roles) {
    return error ? (
      <LoadError title="Could not load roles" error={error} onRetry={load} />
    ) : (
      <Skeleton className="h-64" />
    )
  }

  if (!roles.length) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <BriefcaseIcon />
          </EmptyMedia>
          <EmptyTitle>No roles yet</EmptyTitle>
          <EmptyDescription>
            Load the data pack with <code>uv run python -m app.seed</code>.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles</CardTitle>
        <CardDescription>
          Pick a role to review its candidates. Counts cover the answers that
          count.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error !== null && (
          <LoadError title="Could not refresh" error={error} onRetry={load} />
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Role</TableHead>
              <TableHead>Candidates</TableHead>
              <TableHead>Answers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.map((role) => (
              <TableRow key={role.id}>
                <TableCell>
                  <Link
                    href={`/hr/roles/${role.id}`}
                    className="font-medium underline-offset-4 hover:underline"
                  >
                    {role.name}
                  </Link>
                </TableCell>
                <TableCell>{role.candidates}</TableCell>
                <TableCell>
                  <StatusCounts counts={role.counts} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
