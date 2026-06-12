"use client";

import { useEffect, useRef } from "react";
import type { ComponentPropsWithoutRef, ReactElement, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { CopyButton } from "@/components/ui/copy-button";
import type { BusinessGoalsUpdate } from "@/types";
import type { ChatMessage, StartRoute } from "@/hooks/use-prompter";
import { DraftProposalCard } from "./draft-proposal-card";
import { GoalEditCard } from "./goal-edit-card";

interface ChatMessagesProps {
  messages: ChatMessage[];
  onStart: (route: StartRoute) => void;
  onKeepChatting: () => void;
  isLaunching?: boolean;
  /** Apply a Secretary-proposed goal edit (CEO confirm → PUT /goals). */
  onConfirmGoalEdit: (messageId: string, patch: BusinessGoalsUpdate) => void;
  onDismissGoalEdit: (messageId: string) => void;
  /** Id of the message whose goal-edit confirm is mid-flight, if any. */
  confirmingGoalEditId?: string | null;
  /** Empty-state hint when the conversation hasn't started yet. */
  emptyState?: ReactNode;
}

/** Raw text of a fenced code block — the <pre>'s <code> child's string content. */
function codeText(children: ReactNode): string {
  const codeEl = children as ReactElement<{ children?: ReactNode }> | undefined;
  const inner = codeEl?.props?.children;
  if (typeof inner === "string") return inner;
  if (Array.isArray(inner)) {
    return inner.filter((c): c is string => typeof c === "string").join("");
  }
  return "";
}

// Copy lives on KEY PARTS only: fenced code blocks here, and the draft card has
// its own. (Not a blanket button on every whole message.)
const markdownComponents = {
  pre(props: ComponentPropsWithoutRef<"pre">) {
    const text = codeText(props.children).replace(/\n$/, "");
    return (
      <div className="group relative">
        <pre {...props} />
        {text && (
          <CopyButton
            value={text}
            className="absolute right-1.5 top-1.5 bg-background/80 opacity-0 transition-opacity group-hover:opacity-100"
          />
        )}
      </div>
    );
  },
};

/** GFM markdown that inherits the bubble's text color, so it renders correctly on
 *  both the muted assistant bubble and the primary user bubble (lists, code,
 *  newlines all preserved). */
function MarkdownBody({ content }: { content: string }) {
  return (
    <div className="prose prose-sm max-w-none !text-inherit [&_*]:!text-inherit prose-p:my-1.5 prose-headings:mt-3 prose-headings:mb-1 prose-pre:my-2 prose-pre:bg-black/20">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function ChatMessages({
  messages,
  onStart,
  onKeepChatting,
  isLaunching,
  onConfirmGoalEdit,
  onDismissGoalEdit,
  confirmingGoalEditId,
  emptyState,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-muted-foreground px-8">
        {emptyState ?? (
          <>
            <p className="text-lg font-semibold">How can I help?</p>
            <p className="text-sm max-w-md">
              Ask how things are going, set a goal, nudge an agent, or describe
              work you want done — I&apos;ll handle it or bring it to you.
            </p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
      {messages.map((msg) => {
        if (msg.role === "user") {
          return (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[70%] rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm text-primary-foreground">
                <MarkdownBody content={msg.content} />
              </div>
            </div>
          );
        }

        if (msg.role === "error") {
          return (
            <div key={msg.id} className="flex justify-start">
              <div className="flex max-w-[70%] items-start gap-2 rounded-2xl rounded-tl-sm border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{msg.content}</span>
              </div>
            </div>
          );
        }

        // Assistant message
        const hasCard = Boolean(msg.draft || msg.goalEdit);
        return (
          <div key={msg.id} className="flex flex-col gap-2">
            {/* Render the text bubble only when there's actual content — a
                card-only message (draft / goal-edit) or a now-cleared card would
                otherwise show a blank pill. */}
            {msg.content.trim() && (
              <div className="flex justify-start">
                <div
                  className={cn(
                    "max-w-[70%] rounded-2xl rounded-tl-sm bg-muted px-4 py-3 text-sm text-foreground",
                    hasCard && "max-w-[85%]"
                  )}
                >
                  <MarkdownBody content={msg.content} />
                </div>
              </div>
            )}

            {/* Inline draft proposal card when the Secretary offers a draft */}
            {msg.draft && (
              <div className="flex justify-start">
                <div className="w-full max-w-[85%]">
                  <DraftProposalCard
                    draft={msg.draft}
                    onKeepChatting={onKeepChatting}
                    onStart={onStart}
                    isLaunching={isLaunching}
                  />
                </div>
              </div>
            )}

            {/* Inline goal-edit confirm card when the Secretary proposes one */}
            {msg.goalEdit && (
              <div className="flex justify-start">
                <div className="w-full max-w-[85%]">
                  <GoalEditCard
                    patch={msg.goalEdit}
                    onConfirm={() => onConfirmGoalEdit(msg.id, msg.goalEdit!)}
                    onDismiss={() => onDismissGoalEdit(msg.id)}
                    isConfirming={confirmingGoalEditId === msg.id}
                  />
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </div>
  );
}
