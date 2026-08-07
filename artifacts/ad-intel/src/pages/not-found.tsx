import { Link } from "wouter";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
      <h1 className="text-4xl font-bold tracking-tight">404</h1>
      <p className="text-muted-foreground">The page you're looking for doesn't exist.</p>
      <Link href="/" className="text-primary hover:underline">
        Return to Dashboard
      </Link>
    </div>
  );
}
