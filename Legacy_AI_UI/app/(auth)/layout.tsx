export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="relative min-h-screen bg-[var(--bg)] overflow-hidden">
      <div className="relative z-10 min-h-screen">{children}</div>
    </div>
  )
}
