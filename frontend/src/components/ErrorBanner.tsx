export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) {
    return null
  }
  return (
    <p className="banner error" role="alert">
      {message}
    </p>
  )
}
