import { CandidateInterview } from "./candidate-interview"

export default async function Page({
  params,
}: {
  params: Promise<{ token: string }>
}) {
  const { token } = await params
  return <CandidateInterview token={token} />
}
