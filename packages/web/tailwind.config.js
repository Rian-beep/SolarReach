/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // App-level surfaces — names deliberately avoid Tailwind utility tokens.
        "app-bg": "#070B14",
        "gotham-dark": "#0F1422",
        "gotham-mid": "#161B2C",
        "gotham-line": "#212741",
        "solar-amber": "#F5A524",
        "solar-magenta": "#E6428E",
        "solar-emerald": "#10B981",
        "solar-red": "#EF4444",
        "ink-primary": "#E6ECF8",
        "ink-secondary": "#A1ABC4",
        "ink-muted": "#6B7591",
        "accent-blue": "#3B82F6",
        "accent-violet": "#8B5CF6",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        cockpit: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.45)",
        "amber-glow": "0 0 0 1px rgba(245,165,36,0.4), 0 0 24px rgba(245,165,36,0.25)",
        "magenta-glow": "0 0 0 1px rgba(230,66,142,0.5), 0 0 32px rgba(230,66,142,0.35)",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(230,66,142,0.55)" },
          "50%": { boxShadow: "0 0 0 8px rgba(230,66,142,0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        slideInRight: {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 1.6s ease-in-out infinite",
        shimmer: "shimmer 1.6s linear infinite",
        "slide-in-right": "slideInRight 320ms cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
