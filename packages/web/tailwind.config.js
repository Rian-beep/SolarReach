/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Ground
        "app-void": "#050608",
        "app-surface": "#0A0E14",
        "app-elev-1": "#0F141C",
        "app-elev-2": "#131A24",

        // Borders / chrome
        iron: "#1A2230",
        "iron-bright": "#2A3445",
        "iron-grid": "#131C2A",

        // Text — names avoid colliding with Tailwind utility tokens
        bone: "#E8EDF5",
        mute: "#93A3B8",
        dim: "#5A6878",
        grid: "#3A4658",

        // Accents
        cyan: "#1FB6FF",
        "cyan-glow": "#1FB6FF40",
        amber: "#FFB020",
        "amber-glow": "#FFB02033",
        red: "#FF4757",
        emerald: "#20D082",
        magenta: "#F040C0",

        // Score gradient
        "score-low": "#FF4757",
        "score-mid": "#FFB020",
        "score-high": "#20D082",

        // ── Legacy aliases (keep older code building until full sweep lands) ──
        "app-bg": "#050608",
        "gotham-dark": "#0A0E14",
        "gotham-mid": "#0F141C",
        "gotham-line": "#1A2230",
        "solar-amber": "#FFB020",
        "solar-magenta": "#F040C0",
        "solar-emerald": "#20D082",
        "solar-red": "#FF4757",
        "ink-primary": "#E8EDF5",
        "ink-secondary": "#93A3B8",
        "ink-muted": "#5A6878",
        "accent-blue": "#1FB6FF",
        "accent-violet": "#F040C0",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "Menlo", "monospace"],
      },
      fontSize: {
        // Tighter scale per Gotham spec
        xs: ["11px", { lineHeight: "16px" }],
        sm: ["12px", { lineHeight: "16px" }],
        base: ["13px", { lineHeight: "18px" }],
        md: ["14px", { lineHeight: "20px" }],
        lg: ["16px", { lineHeight: "24px" }],
        xl: ["20px", { lineHeight: "28px" }],
        "2xl": ["28px", { lineHeight: "32px" }],
        display: ["40px", { lineHeight: "44px", letterSpacing: "-0.01em" }],
      },
      letterSpacing: {
        tight: "-0.01em",
        wide: "0.04em",
        widest: "0.08em",
      },
      borderRadius: {
        DEFAULT: "2px",
        sm: "2px",
        md: "2px",
        lg: "4px",
        xl: "4px",
        "2xl": "4px",
      },
      spacing: {
        // Dense scale alongside default — components prefer 4/8/12/16
      },
      boxShadow: {
        cockpit: "0 0 0 1px rgba(42,52,69,0.6) inset",
        "cyan-inset": "inset 0 0 0 1px rgba(31,182,255,0.3)",
        "drawer-overlay": "0 0 64px -16px rgba(0,0,0,0.8)",
        "amber-glow": "0 0 0 1px rgba(255,176,32,0.5)",
        "magenta-glow": "0 0 0 1px rgba(240,64,192,0.5)",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        "live-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.5", transform: "scale(0.85)" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "caret-blink": {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
      },
      animation: {
        shimmer: "shimmer 1.5s linear infinite",
        "pulse-soft": "pulse-soft 1s linear infinite",
        "live-dot": "live-dot 1s linear infinite",
        "slide-in-right": "slide-in-right 200ms ease-out",
        "fade-in": "fade-in 120ms ease-out",
        "caret-blink": "caret-blink 1.1s steps(2, end) infinite",
      },
    },
  },
  plugins: [],
};
