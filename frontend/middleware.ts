import { clerkMiddleware } from "@clerk/nextjs/server";

// All routes are public — anonymous users can use the chat.
// Clerk middleware runs on every request so useUser() / useAuth()
// work correctly throughout the app (Perplexity model).
export default clerkMiddleware();

export const config = {
  matcher: [
    // Always run middleware for Clerk's own proxy paths (/__clerk/*).
    // These must NOT be excluded even though they contain .js extensions.
    "/__clerk/(.*)",
    // Skip Next.js internals and static files, but run for everything else.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes.
    "/(api|trpc)(.*)",
  ],
};
