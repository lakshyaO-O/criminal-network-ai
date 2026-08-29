/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        workspace: {
          bg: "#0e0e10",
          panel: "#17171a",
          border: "#262629",
          muted: "#8a8a90",
          subtle: "#1e1e22",
          accent: "#d8d8dc",
          accent2: "#9aa0a6"
        }
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"]
      },
      borderRadius: {
        xs: "6px",
        sm: "8px"
      }
    }
  },
  plugins: []
};
