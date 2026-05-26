/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // EDA / GitHub Dark inspired
        eda: {
          bg: '#0d1117',
          'bg-secondary': '#161b22',
          'bg-tertiary': '#21262d',
          border: '#30363d',
          'border-hover': '#8b949e',
          text: '#f0f6fc',
          'text-secondary': '#8b949e',
          'text-tertiary': '#6e7681',
          accent: '#58a6ff',
          success: '#3fb950',
          warning: '#d29922',
          error: '#f85149',
          'accent-hover': '#79c0ff',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xs': '0.70rem',
        'sm': '0.80rem',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.2s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateY(-4px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}
