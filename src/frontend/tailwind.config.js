/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'clilens-teal': {
          50: '#e0f2f7',
          100: '#b3dfe9',
          200: '#80cbdb',
          300: '#4db6cd',
          400: '#26a6c2',
          500: '#0097b7',
          600: '#008aaa',
          700: '#00799a',
          800: '#00698a',
          900: '#004d6d',
        },
        'clilens-primary': '#0097b7',
        'clilens-secondary': '#00799a',
        'clilens-verified': '#10b981',
        'clilens-partial': '#f59e0b',
        'clilens-unverified': '#ef4444',
      },
    },
  },
  plugins: [],
}
