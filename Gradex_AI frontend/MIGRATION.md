# Next.js Migration Guide

This project has been successfully converted from Vite + React to Next.js 15.

## Key Changes

### Project Structure
```
src/
├── app/                          # Next.js App Router
│   ├── (auth)/                   # Auth group route
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── (lecturer)/               # Lecturer-only routes
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── grading-diagram/page.tsx
│   │   ├── grading-handwritten/page.tsx
│   │   ├── analytics/page.tsx
│   │   ├── exam-creator/page.tsx
│   │   └── viva/page.tsx
│   ├── (student)/                # Student-only routes
│   │   ├── layout.tsx
│   │   └── dashboard/page.tsx
│   └── layout.tsx                # Root layout
├── components/                   # React components
├── contexts/                     # Context providers
│   └── AuthContext.tsx
└── styles/                       # Global styles
```

### Configuration Files
- `next.config.ts` - Next.js configuration
- `tsconfig.json` - TypeScript configuration for Next.js
- `tailwind.config.ts` - Tailwind CSS configuration
- `postcss.config.js` - PostCSS configuration

### Deleted Files
- `vite.config.ts` - Vite configuration (no longer needed)
- `src/main.tsx` - Vite entry point (no longer needed)

## How Routing Works

### Authentication
- All unauthenticated users start at `/` which shows the login page
- After login, users are redirected based on their role:
  - **Lecturer**: `/dashboard`
  - **Student**: `/student-dashboard`

### Route Protection
- Lecturer routes are protected by checking `role === "lecturer"` in the layout
- Student routes are protected by checking `role === "student"` in the layout
- Unauthorized access redirects to the login page

### Group Routes (Dynamic Layouts)
- `(auth)` - Routes without sidebar/topbar
- `(lecturer)` - Lecturer routes with full UI
- `(student)` - Student routes with full UI

## Running the App

### Development
```bash
npm run dev
# or
pnpm dev
```
Visit `http://localhost:3000`

### Production Build
```bash
npm run build
npm run start
```

### Lint
```bash
npm run lint
```

## Migration Notes

1. **Import Paths**: All imports use `@/` alias which points to `src/`
2. **Components**: All React components are in `src/components/` and marked as client components where needed with `"use client"`
3. **Styles**: Global styles are imported in the root layout
4. **Environment Variables**: Create a `.env.local` file for environment-specific variables
5. **Authentication**: Currently uses client-side state with React Context. For production, implement proper session management (e.g., next-auth, Clerk, or Auth0)

## Next Steps

For production deployment, consider:
- Implementing persistent authentication (e.g., sessions, JWT, OAuth)
- Adding error handling and error pages
- Setting up API routes for backend integration
- Adding loading states and suspense boundaries
- Implementing image optimization with Next.js Image
- Adding middleware for auth checks
- Setting up monitoring and analytics
