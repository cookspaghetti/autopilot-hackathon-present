/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1536px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-geologica)", "ui-sans-serif", "system-ui"],
        display: ["var(--font-funnel)", "ui-sans-serif", "system-ui"],
      },
      // Responsive Type Scale
      fontSize: {
        "display-1": ["clamp(3rem, 5vw + 1rem, 6rem)", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display-2": ["clamp(2.5rem, 4vw + 1rem, 4.5rem)", { lineHeight: "1.15", letterSpacing: "-0.02em", fontWeight: "600" }],
        "display-3": ["clamp(2rem, 3vw + 1rem, 3.75rem)", { lineHeight: "1.2", letterSpacing: "-0.01em", fontWeight: "600" }],
        "display-4": ["2.5rem", { lineHeight: "1.2", letterSpacing: "-0.01em", fontWeight: "500" }],
        "display-5": ["2rem", { lineHeight: "1.2", letterSpacing: "0em", fontWeight: "500" }],
        "display-6": ["1.5rem", { lineHeight: "1.2", letterSpacing: "0em", fontWeight: "500" }],
        // Micro labels for stats
        "micro": ["0.6875rem", { lineHeight: "1.4", letterSpacing: "0.1em", fontWeight: "600" }],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Brand Palette for manual usage
        brand: {
          black: "#04060A",
          navy: "#141A42",
          cornflower: "#8AA2DF",
          muted: "#848EAA",
          purple: "#535EA4",
          light: "#E7E7E7",
          // Additional shades for UI
          "navy-light": "#1E2654",
          "cornflower-light": "#A8BCEB",
        }
      },
      // Background gradients
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #141A42 0%, #535EA4 100%)',
        'brand-mesh': 'radial-gradient(at 0% 0%, #535EA4 0px, transparent 50%), radial-gradient(at 100% 100%, #141A42 0px, transparent 50%)',
        'glass-gradient': 'linear-gradient(180deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)',
        'glaze': 'linear-gradient(180deg, #FFFFFF 0%, #F8FAFF 100%)',
        'shimmer': 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
      },
      // Modern shadow system: strokes + glows instead of heavy shadows
      boxShadow: {
        'none': 'none',
        // Glass effect: inner highlight + subtle border
        'glass': 'inset 0 1px 0 0 rgba(255,255,255,0.8), 0 0 0 1px rgba(0,0,0,0.03)',
        'glass-hover': 'inset 0 1px 0 0 rgba(255,255,255,0.9), 0 0 0 1px rgba(138,162,223,0.3)',
        // Accent glow for interactive elements
        'accent': '0 0 0 1px rgba(138,162,223,0.3), 0 0 20px -5px rgba(138,162,223,0.15)',
        'accent-strong': '0 0 0 1px rgba(138,162,223,0.5), 0 0 30px -5px rgba(138,162,223,0.25)',
        // Floating elevation for detached elements
        'float': '0 8px 30px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.03)',
        'float-lg': '0 12px 40px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.03)',
        // Legacy soft shadows (kept for compatibility)
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'medium': '0 4px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 30px -5px rgba(0, 0, 0, 0.05)',
        // Inner shadow for inputs
        'inner-soft': 'inset 0 1px 2px rgba(0,0,0,0.05)',
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      // Comprehensive keyframes library
      keyframes: {
        // Accordion (existing)
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        // Fade animations
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "fade-out": {
          "0%": { opacity: "1" },
          "100%": { opacity: "0" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-down": {
          "0%": { opacity: "0", transform: "translateY(-10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Scale animations
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "scale-out": {
          "0%": { opacity: "1", transform: "scale(1)" },
          "100%": { opacity: "0", transform: "scale(0.95)" },
        },
        // Slide animations
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
        "slide-out-right": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(100%)" },
        },
        "slide-in-left": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(0)" },
        },
        "slide-in-bottom": {
          "0%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0)" },
        },
        "slide-in-top": {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(0)" },
        },
        // Number count-up entrance
        "count-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Shimmer for loading states
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        // Pulse ring for status indicators
        "pulse-ring": {
          "0%": { transform: "scale(0.8)", opacity: "0.5" },
          "100%": { transform: "scale(2)", opacity: "0" },
        },
        // Ambient blob animation
        "blob": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%": { transform: "translate(30px, -50px) scale(1.1)" },
          "66%": { transform: "translate(-20px, 20px) scale(0.9)" },
        },
        // Float animation (existing)
        "float": {
          "0%, 100%": { transform: "translate(0, 0)" },
          "50%": { transform: "translate(10px, 20px)" },
        },
        // Spin (for loaders)
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        // Bounce subtle
        "bounce-subtle": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-5px)" },
        },
        // Notification badge bounce
        "badge-bounce": {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.2)" },
        },
      },
      // Animation utilities
      animation: {
        // Accordion
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        // Fade
        "fade-in": "fade-in 0.3s ease-out",
        "fade-out": "fade-out 0.3s ease-out",
        "fade-up": "fade-up 0.4s ease-out",
        "fade-down": "fade-down 0.4s ease-out",
        // Scale
        "scale-in": "scale-in 0.2s ease-out",
        "scale-out": "scale-out 0.2s ease-out",
        // Slide
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "slide-out-right": "slide-out-right 0.3s ease-out",
        "slide-in-left": "slide-in-left 0.3s ease-out",
        "slide-in-bottom": "slide-in-bottom 0.3s ease-out",
        "slide-in-top": "slide-in-top 0.3s ease-out",
        // Count-up
        "count-up": "count-up 0.5s ease-out",
        // Shimmer
        "shimmer": "shimmer 2s infinite linear",
        // Status indicators
        "pulse-ring": "pulse-ring 1.5s ease-out infinite",
        "badge-bounce": "badge-bounce 0.3s ease-out",
        // Ambient blobs
        "blob": "blob 7s infinite",
        "blob-delayed": "blob 8s infinite reverse",
        // Float
        "float": "float 10s ease-in-out infinite",
        "float-delayed": "float 12s ease-in-out infinite reverse",
        // Spin
        "spin-slow": "spin-slow 3s linear infinite",
        // Bounce
        "bounce-subtle": "bounce-subtle 2s ease-in-out infinite",
      },
      // Transition timing functions
      transitionTimingFunction: {
        'bounce-in': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      // Z-index scale
      zIndex: {
        'dropdown': '50',
        'sticky': '100',
        'fixed': '200',
        'modal-backdrop': '300',
        'modal': '400',
        'popover': '500',
        'tooltip': '600',
        'toast': '700',
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("tailwindcss-animate")],
}
