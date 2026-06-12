"use client";

import Link from "next/link";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  Compass,
  Inbox,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { useSecretaryDigest } from "@/hooks/use-secretary-digest";
import type {
  SecretaryDigest,
  SecretaryFeedItem,
} from "@/lib/api/secretary";

// ---------------------------------------------------------------------------
// Proactive feed (3.A2) — a compact notifications-style strip in the Secretary
// surface. Surfaces "what needs the CEO": pending approvals, decisions going
// stale, drift off-goal, fresh pitches. So nothing important waits unseen
// (INTENT.md §3 — "Reminds the CEO").
// ---------------------------------------------------------------------------

function itemLabel(item: SecretaryFeedItem): string {
  return item.title || item.subject || "Untitled item";
}

function itemHref(item: SecretaryFeedItem): string | null {
  if (item.task_id) return `/tasks/${item.task_id}`;
  if (item.related_task_id) return `/tasks/${item.related_task_id}`;
  if (item.source === "notification") return "/notifications";
  return null;
}

function FeedRow({
  icon: Icon,
  tone,
  label,
  reason,
  href,
}: {
  icon: typeof Bell;
  tone: "amber" | "violet";
  label: string;
  reason: string;
  href: string | null;
}) {
  const body = (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-md border px-3 py-2 text-sm transition-colors",
        tone === "amber"
          ? "border-amber-500/30 bg-amber-500/5"
          : "border-violet-500/30 bg-violet-500/5",
        href && "hover:bg-muted/60"
      )}
    >
      <Icon
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          tone === "amber" ? "text-amber-500" : "text-violet-500"
        )}
      />
      <div className="min-w-0">
        <p className="truncate font-medium">{label}</p>
        <p className="truncate text-xs text-muted-foreground">{reason}</p>
      </div>
    </div>
  );
  return href ? (
    <Link href={href} className="block">
      {body}
    </Link>
  ) : (
    body
  );
}

function driftSignals(digest: SecretaryDigest): string[] {
  const out: string[] = [];
  if (digest.drift.work_without_objectives) {
    out.push(
      `${digest.drift.in_flight_tasks} task(s) in flight with no active objective behind them`
    );
  }
  if (digest.drift.objectives_without_work) {
    out.push(
      `${digest.drift.active_objectives} active objective(s) with no work in flight`
    );
  }
  return out;
}

export function ProactiveFeed() {
  const { data: digest, isLoading, isError } = useSecretaryDigest();

  return (
    <div className="border-b bg-muted/30 px-6 py-3">
      <div className="mb-2 flex items-center gap-2">
        <Inbox className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          What needs you
        </h2>
        {digest && digest.pending_approvals > 0 && (
          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
            {digest.pending_approvals} pending
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : isError ? (
        <p className="text-xs text-muted-foreground">
          Proactive feed unavailable — the orchestrator may be offline.
        </p>
      ) : digest ? (
        <SecretaryFeedBody digest={digest} />
      ) : null}
    </div>
  );
}

function SecretaryFeedBody({ digest }: { digest: SecretaryDigest }) {
  const drift = driftSignals(digest);
  const isEmpty =
    digest.fresh_pitches.length === 0 &&
    digest.stale_decisions.length === 0 &&
    drift.length === 0;

  if (isEmpty) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
        <span>Nothing needs you right now — the queue is clear.</span>
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {digest.fresh_pitches.map((item) => (
        <FeedRow
          key={`pitch-${item.task_id ?? item.notification_id}`}
          icon={Bell}
          tone="violet"
          label={itemLabel(item)}
          reason={item.reason}
          href={itemHref(item)}
        />
      ))}
      {digest.stale_decisions.map((item) => (
        <FeedRow
          key={`stale-${item.task_id ?? item.notification_id}`}
          icon={Clock}
          tone="amber"
          label={itemLabel(item)}
          reason={`Going stale — ${item.reason}`}
          href={itemHref(item)}
        />
      ))}
      {drift.map((signal) => (
        <FeedRow
          key={`drift-${signal}`}
          icon={signal.includes("no active objective") ? AlertTriangle : Compass}
          tone="amber"
          label="Off-goal drift"
          reason={signal}
          href="/goals"
        />
      ))}
    </div>
  );
}
