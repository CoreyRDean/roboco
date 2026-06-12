"use client";

import { Loader2, Headset, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrompter } from "@/hooks/use-prompter";
import { ChatMessages, ChatComposer, SuccessCard } from "@/components/prompter";
import { ProactiveFeed, ScopePicker } from "@/components/secretary";

// The Secretary — the CEO's ONE-STOP conversational chief-of-staff (INTENT.md
// §3). It opens STRAIGHT into a free chat: the CEO types anything ("how are we
// doing?", "create a task to…", "nudge be-dev-1", "raise the budget to 400") and
// the Secretary answers or acts (directly when in-bounds, surfacing gated things
// to the CEO). The live session is spawned lazily on the first message; the
// proactive feed sits above as a notifications strip so nothing waits unseen.
//
// Task-drafting is now an OPTIONAL in-chat affordance (the ScopePicker), not the
// entrance — attach a project/product only when the CEO wants a SCOPED draft. The
// transport is unchanged (usePrompter / the prompter live relay).
export default function SecretaryPage() {
  const {
    state,
    messages,
    isSending,
    activity,
    createdTaskId,
    createdTaskTitle,
    createdTaskTeam,
    targetKind,
    setTargetKind,
    projectId,
    setProjectId,
    productId,
    setProductId,
    send,
    keepChatting,
    launchTask,
    confirmGoalEdit,
    dismissGoalEdit,
    confirmingGoalEditId,
    startAnother,
    isLaunching,
  } = usePrompter();

  const isSuccess = state === "success";
  // The chat exists from the first message; before that there's no session yet.
  const hasStarted = messages.length > 0 || state !== "idle";
  // Scope locks once the session is live (the repo is already cloned).
  const scopeLocked = hasStarted && state !== "idle";
  const isComposerDisabled = state === "launching" || isSuccess || isSending;

  return (
    <div className="flex h-full flex-col">
      {/* Page header */}
      <div className="flex items-center gap-3 border-b px-6 py-4">
        <Headset className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-lg font-semibold">Secretary</h1>
          <p className="text-xs text-muted-foreground">
            Your chief-of-staff — ask anything: status, goals, directives, work
          </p>
        </div>
        {/* End chat — reap the agent and clear the conversation. Only meaningful
            once a session is running. */}
        {hasStarted && !isSuccess && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto text-muted-foreground"
            onClick={startAnother}
            disabled={state === "launching"}
          >
            <X className="mr-1 h-4 w-4" />
            End chat
          </Button>
        )}
      </div>

      {/* Proactive feed — always visible above the chat (3.A2). */}
      <ProactiveFeed />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Success overlay — a scoped draft was confirmed into a task. */}
        {isSuccess && createdTaskId && createdTaskTitle && createdTaskTeam ? (
          <div className="flex flex-1 flex-col items-center justify-center px-8 py-8">
            <div className="w-full max-w-md">
              <SuccessCard
                taskId={createdTaskId}
                taskTitle={createdTaskTitle}
                team={createdTaskTeam}
                onStartAnother={startAnother}
              />
            </div>
          </div>
        ) : (
          <ChatMessages
            messages={messages}
            onStart={launchTask}
            onKeepChatting={keepChatting}
            isLaunching={isLaunching}
            onConfirmGoalEdit={confirmGoalEdit}
            onDismissGoalEdit={dismissGoalEdit}
            confirmingGoalEditId={confirmingGoalEditId}
          />
        )}

        {/* Live activity indicator — "watch it work" (prominent) */}
        {activity && !isSuccess && (
          <div className="mx-4 mb-2 flex items-center gap-2.5 rounded-lg border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-medium text-primary">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
            <span>{activity}</span>
          </div>
        )}

        {/* Composer + optional scope affordance */}
        {!isSuccess && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between px-4 pt-1.5">
              <ScopePicker
                targetKind={targetKind}
                onTargetKind={setTargetKind}
                projectId={projectId}
                onProjectId={setProjectId}
                productId={productId}
                onProductId={setProductId}
                locked={scopeLocked}
              />
            </div>
            <ChatComposer
              onSend={send}
              disabled={isComposerDisabled}
              isSending={isSending}
              placeholder="Ask anything, or tell me what to do… (Enter to send, Shift+Enter for newline)"
            />
          </div>
        )}
      </div>
    </div>
  );
}
