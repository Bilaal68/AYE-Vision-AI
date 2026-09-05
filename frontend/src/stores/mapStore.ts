import { create } from "zustand";

type MapState = {
  center: [number, number];
  zoom: number;
  setView: (center: [number, number], zoom: number) => void;
};

export const useMapStore = create<MapState>((set) => ({
  center: [9.03, 38.74],
  zoom: 11,
  setView: (center, zoom) => set({ center, zoom }),
}));
