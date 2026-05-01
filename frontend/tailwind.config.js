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
        // Brand → Odoo 19 enterprise purple #714B67.  Reused as `brand-*`
        // so existing className references keep working but render with the
        // new theme.
        brand: {
          50: "#f6f1f4",
          100: "#ead9e3",
          200: "#d2b3c7",
          300: "#b58aa6",
          400: "#956b89",
          500: "#714b67",
          600: "#5a3a52",
          700: "#432c3d",
          800: "#2c1d29",
          900: "#160e14",
        },
        odoo: {
          primary: "#714b67",
          secondary: "#71639e",
          success: "#28a745",
          info: "#17a2b8",
          warning: "#ffac00",
          danger: "#dc3545",
          surface: "#ffffff",
          appBg: "#f6f6f6",
          mutedBg: "#f2f2f2",
          border: "#d9d9d9",
          text: "#212529",
          textMuted: "#6c757d",
        },
      },
      fontFamily: {
        sans: [
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
        // Odoo 19 base is 14px — keep Tailwind's `text-base` aligned.
        base: ["14px", "1.5"],
      },
      spacing: {
        navbar: "46px",
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
