import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 0 0 1px rgba(129, 140, 248, 0.24), 0 22px 70px rgba(15, 23, 42, 0.36)',
      },
      backgroundImage: {
        mesh: 'radial-gradient(circle at 3% 0%, rgba(129, 140, 248, 0.18), transparent 31%), radial-gradient(circle at 86% 6%, rgba(34, 211, 238, 0.12), transparent 24%)',
      },
    },
  },
  plugins: [],
} satisfies Config;
