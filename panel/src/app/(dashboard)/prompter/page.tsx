import { redirect } from "next/navigation";

// The intake "Task Assistant" became the Secretary (Phase 3 — INTENT.md §3).
// Keep the old route working by redirecting it to the relabeled surface so
// bookmarks and in-app links don't 404.
export default function PrompterPage() {
  redirect("/secretary");
}
