/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#0b0f19",
          900: "#111827",
          800: "#1f2937",
        },
      },
    },
  },
  plugins: [],
};
