import { clerkMiddleware } from "@clerk/nextjs/server";

// All routes are public — anonymous users can use the chat.
// Clerk middleware runs on every request so useUser() / useAuth()
// work correctly throughout the app (Perplexity model).
export default clerkMiddleware();

export const config = {
  matcher: [
    // Skip Next.js internals and static files.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes.
    "/(api|trpc)(.*)",
  ],
};
