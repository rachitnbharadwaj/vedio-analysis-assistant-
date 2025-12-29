# YouTube Learning Assistant Frontend

This is the modern web interface for the YouTube Learning Assistant, built with Next.js 16, React 19, and Tailwind CSS. It connects to the Python backend to provide an interactive video analysis experience.

## Features

- **Video Analysis**: Paste a YouTube URL to get a comprehensive topic breakdown.
- **Interactive Chat**: Ask questions about the video content via a chat interface.
- **Smart Summaries**: View timestamped topics and summaries.
- **Modern UI**: Clean, responsive design using Shadcn UI and Tailwind CSS.

## Tech Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router)
- **Library**: [React 19](https://react.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Components**: [Radix UI](https://www.radix-ui.com/) (primitives), [Lucide React](https://lucide.dev/) (icons)
- **Forms**: React Hook Form + Zod

## Getting Started

### Prerequisites

- Node.js (v18 or later recommended)
- npm or pnpm

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   # or
   pnpm install
   ```

### Running the Development Server

1. Start the dev server:
   ```bash
   npm run dev
   # or
   pnpm dev
   ```

2. Open [http://localhost:3000](http://localhost:3000) with your browser to see the application.

## Integration with Backend

This frontend requires the Python backend server to be running.
1. Ensure the backend server is running on `http://localhost:8000` (see `backend/README.md` for instructions).
2. The frontend is configured to communicate with the backend API endpoints (e.g., `/api/analyze`, `/api/chat`).

## Project Structure

- `app/`: Next.js App Router pages and layouts.
- `components/`: Reusable UI components (including Shadcn UI components).
- `lib/`: Utility functions and configuration.
- `public/`: Static assets.
