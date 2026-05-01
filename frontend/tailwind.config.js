/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    screens: {
      xs: "420px",
      sm: "640px",
      md: "768px",
      lg: "1024px",
      xl: "1280px",
      "2xl": "1536px",
    },
    extend: {
      colors: {
        // Brand → SAP Fiori "action blue" #0a6ed1.  Kept under `brand-*` so
        // every component already referencing brand-500/600/etc. re-skins
        // automatically when we swap themes.
        brand: {
          50: "#e8f2fb",
          100: "#cde0f4",
          200: "#9cc1ea",
          300: "#6ba1e0",
          400: "#3b82d6",
          500: "#0a6ed1", // Fiori action blue
          600: "#075ba8",
          700: "#054780",
          800: "#033358",
          900: "#021e35",
        },
        // Fiori semantic palette + Belize Hole navy for the shellbar.
        sap: {
          primary: "#0a6ed1",
          shellbar: "#354a5f", // Belize Hole — top bar bg
          accent: "#5d9ff5",
          success: "#107e3e",
          info: "#0a6ed1",
          warning: "#e9730c",
          danger: "#bb0000",
          surface: "#ffffff",
          appBg: "#f5f6f7",
          mutedBg: "#eef0f2",
          border: "#e5e5e5",
          text: "#32363a",
          textMuted: "#6a6d70",
        },
        // Backwards-compat alias — old code references `odoo-*` classes but
        // resolves to SAP tokens now.  Will be removed once every page is
        // migrated.
        odoo: {
          primary: "#0a6ed1",
          surface: "#ffffff",
          appBg: "#f5f6f7",
          mutedBg: "#eef0f2",
          border: "#e5e5e5",
          text: "#32363a",
          textMuted: "#6a6d70",
        },
      },
      fontFamily: {
        sans: [
          "72", // SAP's house typeface
          "Inter",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "Noto Sans Thai",
          "IBM Plex Sans Thai",
          "system-ui",
          "sans-serif",
        ],
      },
      fontSize: {
        // Fiori uses 14px as the base for content density "Cozy".
        base: ["14px", "1.5"],
      },
      spacing: {
        navbar: "44px",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        floatIn: {
          "0%": { opacity: "0", transform: "translateY(8px) scale(0.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
        "float-in": "floatIn 0.5s ease-out both",
      },
    },
  },
  plugins: [],
};
