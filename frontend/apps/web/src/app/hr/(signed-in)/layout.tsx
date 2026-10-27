import { HrHeader } from "./hr-header"

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <HrHeader />
      {children}
    </div>
  )
}
