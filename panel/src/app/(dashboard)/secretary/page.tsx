"use client";

import { Loader2, Headset, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrompter } from "@/hooks/use-prompter";
import {
  ChatMessages,
  ChatComposer,
  SuccessCard,
  IntakeForm,
} from "@/components/prompter";
import { ProactiveFeed } from "@/components/secretary";

// The Secretary — the CEO's two-way chief-of-staff (INTENT.md §3). The evolution
// of the intake interviewer: it KEEPS its drafting ability (the IntakeForm →
// live chat → draft → launch flow below, driven by usePrompter) and is surfaced
// as a persistent, always-available entry — a top-level nav item plus an
// always-reachable chat — with the proactive feed (3.A2) sitting above it as a
// notifications-style strip so nothing important waits unseen.
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
    initialMessage,
    setInitialMessage,
    isFormValid,
    start,
    send,
    keepChatting,
    launchTask,
    startAnother,
    isLaunching,
  } = usePrompter();

  const showForm = state === "form" || state === "preparing";
  const isComposerDisabled =
    state === "launching" || state === "success" || isSending;

  return (
    <div className="flex h-full flex-col">
      {/* Page header */}
      <div className="flex items-center gap-3 border-b px-6 py-4">
        <Headset className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-lg font-semibold">Secretary</h1>
          <p className="text-xs text-muted-foreground">
            Your chief-of-staff — set goals, get status, clear the queue, draft work
          </p>
        </div>
        {/* End chat — reap the agent and return to the form (any chat state) */}
        {!showForm && state !== "success" && (
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

      {showForm ? (
        <IntakeForm
          targetKind={targetKind}
          onTargetKind={setTargetKind}
          projectId={projectId}
          onProjectId={setProjectId}
          productId={productId}
          onProductId={setProductId}
          initialMessage={initialMessage}
          onInitialMessage={setInitialMessage}
          isValid={isFormValid()}
          isPreparing={state === "preparing"}
          onStart={start}
        />
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Success overlay in chat area */}
          {state === "success" &&
          createdTaskId &&
          createdTaskTitle &&
          createdTaskTeam ? (
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
            />
          )}

          {/* Live activity indicator — "watch it work" (prominent) */}
          {activity && state !== "success" && (
            <div className="mx-4 mb-2 flex items-center gap-2.5 rounded-lg border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-medium text-primary">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
              <span>{activity}</span>
            </div>
          )}

          {/* Composer */}
          {state !== "success" && (
            <ChatComposer
              onSend={send}
              disabled={isComposerDisabled}
              isSending={isSending}
            />
          )}
        </div>
      )}
    </div>
  );
}
