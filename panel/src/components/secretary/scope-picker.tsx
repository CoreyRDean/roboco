"use client";

import { FolderGit2, Boxes, ChevronDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProjects } from "@/hooks/use-projects";
import { useProducts } from "@/hooks/use-products";
import type { TargetKind } from "@/hooks/use-prompter";

interface ScopePickerProps {
  targetKind: TargetKind;
  onTargetKind: (k: TargetKind) => void;
  projectId: string;
  onProjectId: (id: string) => void;
  productId: string;
  onProductId: (id: string) => void;
  /** Once the live session is running the scope is locked in (the repo is
   *  already cloned), so the picker is read-only / disabled. */
  locked?: boolean;
}

/**
 * Optional in-chat scope affordance — NOT the entrance. The Secretary opens into
 * a scopeless free chat; this lets the CEO attach a project/product when they
 * want to draft a *scoped* task (so the agent clones that repo and can read the
 * code before proposing a draft). Empty scope = the default scopeless chat.
 */
export function ScopePicker({
  targetKind,
  onTargetKind,
  projectId,
  onProjectId,
  productId,
  onProductId,
  locked = false,
}: ScopePickerProps) {
  const { data: projects = [] } = useProjects();
  const { data: products = [] } = useProducts();

  const activeId = targetKind === "product" ? productId : projectId;
  const activeName =
    targetKind === "product"
      ? products.find((p) => p.id === productId)?.name
      : projects.find((p) => p.id === projectId)?.name;
  const hasScope = activeId !== "";

  const clearScope = () => {
    onProjectId("");
    onProductId("");
  };

  const label = hasScope
    ? `${targetKind === "product" ? "Product" : "Project"}: ${activeName ?? "selected"}`
    : "Attach a project";

  return (
    <div className="flex items-center gap-1.5">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
            {targetKind === "product" ? (
              <Boxes className="h-3.5 w-3.5" />
            ) : (
              <FolderGit2 className="h-3.5 w-3.5" />
            )}
            <span className="max-w-[180px] truncate">{label}</span>
            <ChevronDown className="h-3 w-3 opacity-60" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80 space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">Scope a task draft</p>
            <p className="text-xs text-muted-foreground">
              Attach a project or product to draft a scoped task — the agent
              clones it and reads the code. Leave it empty to just chat.
            </p>
          </div>

          <div className="space-y-2">
            <Label className="text-xs">Scope</Label>
            <Tabs
              value={targetKind}
              onValueChange={(v) => onTargetKind(v as TargetKind)}
            >
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="project" disabled={locked}>
                  Single cell
                </TabsTrigger>
                <TabsTrigger value="product" disabled={locked}>
                  Board-led
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {targetKind === "project" ? (
              <Select
                value={projectId}
                onValueChange={onProjectId}
                disabled={locked}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a project…" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <>
                <Select
                  value={productId}
                  onValueChange={onProductId}
                  disabled={locked}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a product…" />
                  </SelectTrigger>
                  <SelectContent>
                    {products.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} ({p.cell_count} cells)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {products.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No products yet — target a single project instead.
                  </p>
                )}
              </>
            )}
          </div>

          {locked && (
            <p className="text-xs text-muted-foreground">
              Scope is locked for this chat. End the chat to change it.
            </p>
          )}
        </PopoverContent>
      </Popover>

      {hasScope && !locked && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground"
          onClick={clearScope}
          aria-label="Clear scope"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}
