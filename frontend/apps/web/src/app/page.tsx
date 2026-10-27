import Link from "next/link"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"

export default function Page() {
  return (
    <Card className="mx-auto max-w-md">
      <CardHeader>
        <CardTitle>AI suggests a score, HR decides</CardTitle>
        <CardDescription>
          Candidates: open the personal link from your interview invite. No
          account needed.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button render={<Link href="/hr" />} nativeButton={false}>
          HR sign in
        </Button>
      </CardFooter>
    </Card>
  )
}
