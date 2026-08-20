/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        minteal: {
          50: '#f2f7f7',
          100: '#dbe5e5',
          200: '#b8d1d0',
          300: '#93bdb7',
          400: '#6f9f9c',
          500: '#4c7c7c',
          600: '#365c5c',
          700: '#243f3f',
          800: '#162c2c',
          900: '#0c1b1b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
