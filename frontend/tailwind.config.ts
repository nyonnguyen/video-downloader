import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        card: "#15181d",
        border: "#24272d",
        muted: "#8b9099",
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
} satisfies Config;
