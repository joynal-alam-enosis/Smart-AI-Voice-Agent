import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        ambient: '0 24px 80px rgba(15, 23, 42, 0.12)',
        lift: '0 14px 40px rgba(15, 23, 42, 0.16)',
      },
      backgroundImage: {
        halo: 'radial-gradient(circle at 18% 14%, rgba(129, 140, 248, 0.22), transparent 26%), radial-gradient(circle at 83% 3%, rgba(45, 212, 191, 0.15), transparent 24%), linear-gradient(135deg, #f8fafc 0%, #f4f7ff 50%, #f8fafc 100%)',
      },
      keyframes: {
        pulseRing: {
          '0%, 100%': { transform: 'scale(0.94)', opacity: '0.35' },
          '50%': { transform: 'scale(1.1)', opacity: '0.06' },
        },
      },
      animation: {
        'pulse-ring': 'pulseRing 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
