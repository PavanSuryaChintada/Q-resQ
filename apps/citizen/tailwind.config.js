/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ground: {
          '000': '#F4F1EA',
          100: '#FFFFFF',
          200: '#E8E3D8',
          300: '#D2CCBE',
          400: '#A8A091',
        },
        ink: {
          '000': '#14181A',
          100: '#3A4145',
          200: '#6B7276',
          300: '#9AA0A3',
        },
        sev: {
          0: '#3D6B4F',
          1: '#B8901F',
          2: '#C26A15',
          3: '#B02E18',
          4: '#6E1810',
        },
        emergency: '#B02E18',
      },
      fontFamily: {
        display: ['"IBM Plex Sans Condensed"', 'sans-serif'],
        body: ['"IBM Plex Sans"', 'sans-serif'],
        data: ['"IBM Plex Mono"', 'monospace'],
      },
      fontSize: {
        '14': '14px',
        '16': '16px',
        '18': '18px',
        '22': '22px',
        '28': '28px',
        '36': '36px',
      },
    },
  },
  plugins: [],
}
