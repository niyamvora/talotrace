import { RoleCandidates } from "./role-candidates"

export default async function Page({
  params,
}: {
  params: Promise<{ role: string }>
}) {
  const { role } = await params
  return <RoleCandidates roleId={role} />
}
