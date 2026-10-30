/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1b2733",
        paper: "#f6f5f1",
        campus: "#296d64",
        mist: "#e7eee9",
      },
    },
  },
  plugins: [],
};
