import { create } from "zustand";

type InvestigationState = {
  selectedId: string | null;
  setSelectedId: (id: string | null) => void;
};

export const useInvestigationStore = create<InvestigationState>((set) => ({
  selectedId: null,
  setSelectedId: (selectedId) => set({ selectedId }),
}));
