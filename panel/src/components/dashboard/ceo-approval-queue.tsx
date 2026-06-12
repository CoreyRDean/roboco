"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  ExternalLink,
  Rocket,
  Lightbulb,
} from "lucide-react";
import Link from "next/link";
import { TaskStatus, Team, type Task } from "@/types";
import type { CellWork } from "@/lib/api/prompter";
import { toast } from "sonner";

interface CeoApprovalQueueProps {
  className?: string;
}

// The structured pitch payload the Board persists under
// `proactive_context.pitch` (see TaskService.create_pitch). A pitch is a
// product proposal, so the queue renders its rationale — the objective served,
// what it builds, the per-cell work, success criteria, and why now — instead of
// a bare title. Mirrors the intake draft shape (CellWork comes from the prompter
// types) so a pitch reads like the draft proposal card it was authored as.
interface PitchContent {
  objective?: string | null;
  what_this_builds?: string[];
  the_work?: CellWork[];
  notes?: string[];
  rationale?: string | null;
  acceptance_criteria?: string[];
}

// `team` values are slugs; render UX/UI specially, title-case the rest.
const cellLabel = (team: string) =>
  team === "ux_ui" ? "UX/UI" : team.charAt(0).toUpperCase() + team.slice(1);

// A pitch is identified by its origin marker; its rationale lives in
// proactive_context.pitch. Returns null for non-pitch tasks so the queue falls
// back to the plain row.
const getPitch = (task: Task): PitchContent | null => {
  if (task.source !== "pitch") return null;
  const pitch = task.proactive_context?.pitch;
  return pitch && typeof pitch === "object" ? (pitch as PitchContent) : null;
};

export function CeoApprovalQueue({ className }: CeoApprovalQueueProps) {
  const queryClient = useQueryClient();
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [actionType, setActionType] = useState<"approve" | "reject" | "start" | null>(null);
  const [notes, setNotes] = useState("");

  // Fetch tasks awaiting CEO approval (the end-of-work, pre-merge gate)
  const { data: tasks, isLoading } = useQuery({
    queryKey: ["tasks", "awaiting-ceo-approval"],
    queryFn: () => tasksApi.getAwaitingCeoApproval(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Fetch tasks waiting on the CEO's Approve & Start (board review done, still
  // PENDING). The orchestrator sets board_review_complete + notifies the CEO
  // but leaves the task pending, so it never appears in the awaiting-ceo list.
  // Surface it here, or the CEO has no idea a task is waiting on them.
  //
  // approve_and_start does NOT change status — it re-targets the task to the
  // Main PM (team → main_pm). So exclude team === MAIN_PM, otherwise an
  // already-approved task stays in this list forever.
  const { data: startTasks } = useQuery({
    queryKey: ["tasks", "awaiting-approve-start"],
    queryFn: async () => {
      const pending = await tasksApi.list({ status: TaskStatus.PENDING });
      return pending.filter(
        (t) => t.board_review_complete === true && t.team !== Team.MAIN_PM,
      );
    },
    refetchInterval: 30000,
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: ({ taskId, notes }: { taskId: string; notes?: string }) =>
      tasksApi.ceoApprove(taskId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task approved and completed");
      closeDialog();
    },
    onError: (error) => {
      toast.error(`Failed to approve: ${error instanceof Error ? error.message : "Unknown error"}`);
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: ({ taskId, notes }: { taskId: string; notes: string }) =>
      tasksApi.ceoReject(taskId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task rejected and sent back for revision");
      closeDialog();
    },
    onError: (error) => {
      toast.error(`Failed to reject: ${error instanceof Error ? error.message : "Unknown error"}`);
    },
  });

  // Approve & Start mutation — hands a board-reviewed task to the Main PM.
  const approveStartMutation = useMutation({
    mutationFn: ({ taskId, notes }: { taskId: string; notes: string }) =>
      tasksApi.approveAndStart(taskId, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task approved and handed to Main PM");
      closeDialog();
    },
    onError: (error) => {
      toast.error(`Failed to approve & start: ${error instanceof Error ? error.message : "Unknown error"}`);
    },
  });

  const openDialog = (task: Task, action: "approve" | "reject" | "start") => {
    setSelectedTask(task);
    setActionType(action);
    setNotes("");
  };

  const closeDialog = () => {
    setSelectedTask(null);
    setActionType(null);
    setNotes("");
  };

  const handleConfirm = () => {
    if (!selectedTask) return;

    if (actionType === "approve") {
      // The approval note is the audit record for merging to production —
      // required and substantive (>= 20 chars), matching the server gate.
      if (notes.trim().length < 20) {
        toast.error("Approval notes are required (>= 20 characters)");
        return;
      }
      approveMutation.mutate({ taskId: selectedTask.id, notes: notes.trim() });
    } else if (actionType === "start") {
      // Server requires substantive approval notes (>= 20 chars).
      if (notes.trim().length < 20) {
        toast.error("Approval notes are required (>= 20 characters)");
        return;
      }
      approveStartMutation.mutate({ taskId: selectedTask.id, notes: notes.trim() });
    } else if (actionType === "reject") {
      if (!notes.trim()) {
        toast.error("Rejection reason is required");
        return;
      }
      rejectMutation.mutate({ taskId: selectedTask.id, notes });
    }
  };

  const getPriorityBadge = (priority: number) => {
    const variants: Record<number, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
      0: { label: "P0", variant: "destructive" },
      1: { label: "P1", variant: "destructive" },
      2: { label: "P2", variant: "secondary" },
      3: { label: "P3", variant: "outline" },
    };
    const { label, variant } = variants[priority] || { label: `P${priority}`, variant: "outline" as const };
    return <Badge variant={variant}>{label}</Badge>;
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            CEO Approval Queue
          </CardTitle>
          <CardDescription>Tasks awaiting your approval</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const pendingTasks = tasks || [];
  const readyToStart = startTasks || [];
  const totalCount = pendingTasks.length + readyToStart.length;

  // Render a pitch's rationale (objective served, what it builds, the per-cell
  // work, success criteria, why now) so the CEO greenlights a credible bet, not
  // a bare title. Follows the draft-proposal-card presentation: objective as the
  // lede, distinct participating cells as badges, success criteria as a checklist.
  const renderPitchRationale = (pitch: PitchContent) => {
    const cells = pitch.the_work ?? [];
    // the_work has one entry per work item, so dedupe to avoid repeating a cell's
    // badge (Backend Backend …).
    const distinctTeams = Array.from(new Set(cells.map((c) => c.team)));
    const criteria = pitch.acceptance_criteria ?? [];
    return (
      <div className="mt-2 space-y-2">
        {pitch.objective && (
          <p className="text-sm text-muted-foreground line-clamp-3">
            {pitch.objective}
          </p>
        )}
        {pitch.what_this_builds && pitch.what_this_builds.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              What it builds
            </p>
            <ul className="space-y-0.5">
              {pitch.what_this_builds.slice(0, 4).map((item, i) => (
                <li key={i} className="text-xs text-foreground line-clamp-2">
                  · {item}
                </li>
              ))}
              {pitch.what_this_builds.length > 4 && (
                <li className="text-xs text-muted-foreground">
                  +{pitch.what_this_builds.length - 4} more…
                </li>
              )}
            </ul>
          </div>
        )}
        {distinctTeams.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              {distinctTeams.length > 1 ? "Board-led across" : "Cell:"}
            </span>
            {distinctTeams.map((team) => (
              <Badge key={team} variant="outline" className="text-xs">
                {cellLabel(team)}
              </Badge>
            ))}
          </div>
        )}
        {criteria.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              Success criteria ({criteria.length})
            </p>
            <ul className="space-y-1">
              {criteria.slice(0, 4).map((criterion, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="mt-0.5 h-3 w-3 shrink-0 rounded-full border border-primary/50 flex items-center justify-center">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary/50" />
                  </span>
                  <span className="text-foreground line-clamp-2">{criterion}</span>
                </li>
              ))}
              {criteria.length > 4 && (
                <li className="text-xs text-muted-foreground pl-5">
                  +{criteria.length - 4} more…
                </li>
              )}
            </ul>
          </div>
        )}
        {pitch.rationale && (
          <p className="text-xs text-muted-foreground italic line-clamp-3">
            Why now: {pitch.rationale}
          </p>
        )}
      </div>
    );
  };

  const renderRow = (task: Task, kind: "start" | "approve") => {
    const pitch = getPitch(task);
    return (
    <div
      key={task.id}
      className="flex items-start justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {getPriorityBadge(task.priority)}
          <Badge variant="outline">{task.team}</Badge>
          {pitch && (
            <Badge variant="secondary" className="gap-1">
              <Lightbulb className="h-3 w-3" />
              Pitch
            </Badge>
          )}
        </div>
        <Link
          href={`/tasks/${task.id}`}
          className="font-medium hover:underline line-clamp-1"
        >
          {task.title}
        </Link>
        {pitch ? (
          renderPitchRationale(pitch)
        ) : (
          task.quick_context && (
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
              {task.quick_context}
            </p>
          )
        )}
      </div>
      <div className="flex items-center gap-2 ml-4 flex-shrink-0">
        <Link href={`/tasks/${task.id}`}>
          <Button variant="ghost" size="sm">
            <FileText className="h-4 w-4" />
          </Button>
        </Link>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => openDialog(task, "reject")}
        >
          <XCircle className="h-4 w-4 mr-1" />
          Reject
        </Button>
        {kind === "start" ? (
          <Button
            size="sm"
            className="bg-blue-600 hover:bg-blue-700"
            onClick={() => openDialog(task, "start")}
          >
            <Rocket className="h-4 w-4 mr-1" />
            Approve &amp; Start
          </Button>
        ) : (
          <Button
            size="sm"
            className="bg-green-600 hover:bg-green-700"
            onClick={() => openDialog(task, "approve")}
          >
            <CheckCircle2 className="h-4 w-4 mr-1" />
            Approve
          </Button>
        )}
      </div>
    </div>
    );
  };

  return (
    <>
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            CEO Approval Queue
            {totalCount > 0 && (
              <Badge variant="secondary" className="ml-2">
                {totalCount}
              </Badge>
            )}
          </CardTitle>
          <CardDescription>Tasks waiting on your decision</CardDescription>
        </CardHeader>
        <CardContent>
          {totalCount === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <CheckCircle2 className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No tasks awaiting approval</p>
            </div>
          ) : (
            <div className="space-y-5">
              {readyToStart.length > 0 && (
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Ready to start · board reviewed
                  </p>
                  {readyToStart.map((task) => renderRow(task, "start"))}
                </div>
              )}
              {pendingTasks.length > 0 && (
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Final approval · work complete
                  </p>
                  {pendingTasks.map((task) => renderRow(task, "approve"))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <Dialog open={!!selectedTask && !!actionType} onOpenChange={() => closeDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionType === "approve"
                ? "Approve Task"
                : actionType === "start"
                  ? "Approve & Start Task"
                  : "Reject Task"}
            </DialogTitle>
            <DialogDescription>
              {actionType === "approve"
                ? "This will complete the task and notify the team."
                : actionType === "start"
                  ? selectedTask && getPitch(selectedTask)
                    ? "Greenlighting this pitch provisions the private repo(s), registers the product, and seeds the first delivery work — then hands off to the Main PM."
                    : "This hands the task to the Main PM to delegate to the cells and begin work."
                  : "This will send the task back for revision."}
            </DialogDescription>
          </DialogHeader>

          {selectedTask && (
            <div className="py-4">
              <div className="flex items-center gap-2 mb-2">
                {getPriorityBadge(selectedTask.priority)}
                <Badge variant="outline">{selectedTask.team}</Badge>
                {getPitch(selectedTask) && (
                  <Badge variant="secondary" className="gap-1">
                    <Lightbulb className="h-3 w-3" />
                    Pitch
                  </Badge>
                )}
              </div>
              <p className="font-medium">{selectedTask.title}</p>
              {(() => {
                const pitch = getPitch(selectedTask);
                return pitch ? (
                  renderPitchRationale(pitch)
                ) : (
                  selectedTask.description && (
                    <p className="text-sm text-muted-foreground mt-2 line-clamp-3">
                      {selectedTask.description}
                    </p>
                  )
                );
              })()}
              <Link
                href={`/tasks/${selectedTask.id}`}
                target="_blank"
                className="text-sm text-primary flex items-center gap-1 mt-2 hover:underline"
              >
                View full details <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="notes">
              {actionType === "reject"
                ? "Reason for rejection (required)"
                : actionType === "start"
                  ? "Approval notes (required, ≥ 20 characters)"
                  : "Notes (optional)"}
            </Label>
            <Textarea
              id="notes"
              placeholder={
                actionType === "reject"
                  ? "Explain what needs to be fixed..."
                  : actionType === "start"
                    ? "Why this is ready to build, scope to hold to, anything the Main PM should know..."
                    : "Add any notes about this approval..."
              }
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={
                approveMutation.isPending ||
                rejectMutation.isPending ||
                approveStartMutation.isPending
              }
              className={
                actionType === "approve"
                  ? "bg-green-600 hover:bg-green-700"
                  : actionType === "start"
                    ? "bg-blue-600 hover:bg-blue-700"
                    : ""
              }
              variant={actionType === "reject" ? "destructive" : "default"}
            >
              {approveMutation.isPending ||
              rejectMutation.isPending ||
              approveStartMutation.isPending
                ? "Processing..."
                : actionType === "approve"
                  ? "Approve & Complete"
                  : actionType === "start"
                    ? "Approve & Start"
                    : "Reject & Request Revision"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
