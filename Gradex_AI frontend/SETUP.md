# Next.js Conversion - Setup Instructions

Your Vite React application has been successfully converted to Next.js 15! Follow these steps to complete the setup and start developing.

## Step 1: Install Dependencies

```bash
# Using pnpm (recommended)
pnpm install

# Or using npm
npm install

# Or using yarn
yarn install
```

## Step 2: Update Component Directives

Some components may need the `"use client"` directive at the top. Add it to:
- `src/components/LoginPage.tsx`
- `src/components/GradingPage.tsx`
- `src/components/ExamCreator.tsx`
- `src/components/VivaPage.tsx`
- `src/components/StudentDashboard.tsx`
- `src/components/LecturerDashboard.tsx`
- `src/components/AnalyticsPage.tsx`

Example:
```typescript
"use client";

import { useState } from "react";
// ... rest of your component code
```

This is needed for components that use React hooks like `useState`, `useEffect`, etc.

## Step 3: Verify Configuration

Check that these files exist in the root directory:
- ✅ `next.config.ts`
- ✅ `tsconfig.json`
- ✅ `tailwind.config.ts`
- ✅ `postcss.config.js`
- ✅ `package.json` (updated)

## Step 4: Start Development Server

```bash
pnpm dev
```

The app will be available at `http://localhost:3000`

## Step 5: Test the Application

1. The app should load the login page
2. Log in as either "lecturer" or "student"
3. Verify navigation between pages works
4. Check that the sidebar and top bar render correctly

## Common Issues and Solutions

### Issue: Components not rendering
**Solution**: Add `"use client"` directive to interactive components

### Issue: Styling not working
**Solution**: Ensure Tailwind CSS classes are applied. Check `tailwind.config.ts` includes your component files

### Issue: Image/asset imports failing
**Solution**: Place static assets in `public/` folder and reference with `/` prefix

### Issue: Environment variables not working
**Solution**: Create `.env.local` file and use `process.env.NEXT_PUBLIC_*` for browser-accessible variables

## What's Different from Vite

| Aspect | Vite | Next.js |
|--------|------|---------|
| Entry point | `src/main.tsx` | `src/app/layout.tsx` |
| Dev server | `npm run dev` | `npm run dev` |
| Build | `npm run build` | `npm run build` |
| Routing | Client-side (React Router) | File-based (App Router) |
| API routes | External server | Built-in API routes |
| Styling | Tailwind (Vite plugin) | Tailwind (PostCSS) |

## Next Steps

1. **Add "use client" directives** to interactive components (Step 2 above)
2. **Test all routes** to ensure navigation works
3. **Update API calls** to use Next.js API routes or adjust endpoints
4. **Add authentication middleware** for better security
5. **Optimize images** using Next.js Image component
6. **Configure environment variables** in `.env.local`

## Documentation

- [Next.js Documentation](https://nextjs.org/docs)
- [App Router Guide](https://nextjs.org/docs/app)
- [Tailwind CSS with Next.js](https://tailwindcss.com/docs/guides/nextjs)

## Troubleshooting

If you encounter any issues during development:

1. Clear `.next` folder: `rm -r .next` (or `rmdir /s /q .next` on Windows)
2. Clear node_modules and reinstall: `rm -r node_modules && pnpm install`
3. Check the browser console for errors
4. Check the terminal for build errors

Good luck with your Next.js migration! 🚀
