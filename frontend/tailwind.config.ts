import type { Config } from "tailwindcss";

// Minimal base config. shadcn/ui extends theme tokens (colors, radius, keyframes)
// here when components are added via `pnpm dlx shadcn@latest add <name>`.
const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
