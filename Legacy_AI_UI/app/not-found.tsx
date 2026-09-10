import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg)]">
      <div className="text-center max-w-md mx-auto px-6">
        <h1 className="text-6xl font-bold text-violet-600 mb-4">404</h1>
        <h2 className="text-2xl font-bold text-[var(--text-1)] mb-2">
          Page not found
        </h2>
        <p className="text-[var(--text-2)] mb-8">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link href="/login">
          <Button className="bg-violet-600 hover:bg-violet-700 text-white">
            Go back home
          </Button>
        </Link>
      </div>
    </div>
  )
}
