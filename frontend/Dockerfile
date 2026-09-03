FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN npm install -g pnpm@9.12.3 && pnpm install --no-frozen-lockfile

# Copy application code
COPY . .

# Build Next.js app
RUN pnpm run build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Install pnpm (same version that generated the lockfile)
RUN npm install -g pnpm@9.12.3

# Single non-recursive chown (instant) — everything below is created as node,
# so no slow `chown -R` over node_modules/.next is ever needed.
RUN chown node:node /app

USER node
COPY --chown=node:node package.json pnpm-lock.yaml ./
RUN pnpm install --prod --no-frozen-lockfile

# Copy built application (owned by node via --chown)
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/public ./public

EXPOSE 3000

CMD ["pnpm", "start"]
