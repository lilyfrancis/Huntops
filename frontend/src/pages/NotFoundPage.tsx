import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg text-center">
      <p className="eyebrow">404</p>
      <h1 className="text-2xl text-ink">This page doesn't exist</h1>
      <Button asChild size="sm">
        <Link to="/">Back home</Link>
      </Button>
    </div>
  );
}
