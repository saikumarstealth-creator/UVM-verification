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
        'glow': 'glow 2s ease-in-out infinite alternate',
        'shimmer': 'shimmer 2s linear infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'highlight-fade': 'highlightFade 1.5s ease-out forwards',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'bounce-in': 'bounceIn 0.4s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateY(-4px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(88, 166, 255, 0.2), 0 0 10px rgba(88, 166, 255, 0.1)' },
          '100%': { boxShadow: '0 0 12px rgba(88, 166, 255, 0.4), 0 0 24px rgba(88, 166, 255, 0.15)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        highlightFade: {
          '0%': { backgroundColor: 'rgba(210, 153, 34, 0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        bounceIn: {
          '0%': { transform: 'scale(0.9)', opacity: '0' },
          '50%': { transform: 'scale(1.05)' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      }
    },
  },
  plugins: [],
}
