# AutoPilot Command Center - Frontend

A [Next.js](https://nextjs.org) application built with React 19, TypeScript, and Tailwind CSS.

## Getting Started

First, install dependencies:

```bash
npm install
```

Then, run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server with Turbopack |
| `npm run build` | Build for production |
| `npm start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm run format` | Format code with Prettier |

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

## Project Structure

```
src/
├── app/           # App Router pages
├── components/    # React components
│   ├── ai/        # AI-related components
│   ├── layout/    # Layout components (Header, Sidebar)
│   ├── ui/        # Reusable UI components
│   └── brand/     # Branding components
├── context/       # React contexts (AIContext)
├── hooks/         # Custom React hooks
├── lib/           # Utilities and API client
└── middleware.ts  # Auth middleware
```
