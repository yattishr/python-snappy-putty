We need to improve Snappy's project inspection for Node.js / JavaScript / TypeScript projects.

Current issue:
- In a Node.js project, `snappy inspect files` only shows `package.json`.
- This means Snappy does not gather enough source files for context discovery.
- This could weaken `help me...` workflows because the planner may only see project metadata, not actual implementation files.

Goal:
Teach Snappy to detect and include common JavaScript/TypeScript project files while still excluding noisy folders.

Please update the project inspection logic, likely in `src/snappy_putty/project_inspector.py`.

Requirements:

1. Add Node/JavaScript/TypeScript project markers:
   - package.json
   - package-lock.json
   - pnpm-lock.yaml
   - yarn.lock
   - tsconfig.json
   - jsconfig.json
   - vite.config.js
   - vite.config.ts
   - next.config.js
   - next.config.mjs
   - next.config.ts
   - nuxt.config.js
   - nuxt.config.ts
   - eslint.config.js
   - eslint.config.mjs
   - .eslintrc
   - .eslintrc.json
   - tailwind.config.js
   - tailwind.config.ts
   - postcss.config.js

2. Ensure `inspect files` includes relevant source files:
   - .js
   - .jsx
   - .ts
   - .tsx
   - .mjs
   - .cjs
   - .vue
   - .svelte
   - .json
   - .css
   - .scss
   - .html

3. Exclude noisy or generated directories:
   - node_modules
   - .next
   - dist
   - build
   - coverage
   - .turbo
   - .vite
   - out
   - .cache
   - .parcel-cache

4. Keep existing Python project inspection behavior unchanged.

5. Add or update tests covering:
   - A Node project with package.json and src/index.js
   - A TypeScript project with tsconfig.json and src/App.tsx
   - Exclusion of node_modules and build output
   - Existing Python project inspection still passes

6. Run:
   - python -m py_compile src/snappy_putty/project_inspector.py
   - pytest

Expected result:
- `snappy inspect files` in a Node app should show package.json plus relevant source/config files.
- It must not include node_modules or build artifacts.
- Existing behavior must remain stable.
