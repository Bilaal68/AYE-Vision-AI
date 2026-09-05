import { create } from "zustand";

type AlertState = {
  unreadCount: number;
  setUnreadCount: (count: number) => void;
};

export const useAlertStore = create<AlertState>((set) => ({
  unreadCount: 0,
  setUnreadCount: (unreadCount) => set({ unreadCount }),
}));
