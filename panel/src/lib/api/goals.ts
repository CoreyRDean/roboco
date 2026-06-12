import api from "./client";
import type { BusinessGoals, BusinessGoalsUpdate } from "@/types";

export const goalsApi = {
  // Read the company charter (any authenticated agent orients to it)
  get: async (): Promise<BusinessGoals> => {
    const { data } = await api.get<BusinessGoals>("/goals");
    return data;
  },

  // Revise the charter (CEO-only; patch semantics — only present fields apply)
  update: async (updates: BusinessGoalsUpdate): Promise<BusinessGoals> => {
    const { data } = await api.put<BusinessGoals>("/goals", updates);
    return data;
  },
};
