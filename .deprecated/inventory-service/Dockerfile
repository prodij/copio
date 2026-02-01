# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy workspace config
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY tsconfig.base.json ./

# Copy package sources
COPY packages/core ./packages/core
COPY packages/inventory-service ./packages/inventory-service

# Install dependencies
RUN pnpm install --frozen-lockfile

# Build core first, then inventory service
RUN pnpm --filter @copio/core build
RUN pnpm --filter @copio/inventory-service build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy workspace config
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./

# Copy built packages
COPY --from=builder /app/packages/core/dist ./packages/core/dist
COPY --from=builder /app/packages/core/package.json ./packages/core/
COPY --from=builder /app/packages/inventory-service/dist ./packages/inventory-service/dist
COPY --from=builder /app/packages/inventory-service/package.json ./packages/inventory-service/

# Install production dependencies only
RUN pnpm install --frozen-lockfile --prod

# Set environment
ENV NODE_ENV=production
ENV PORT=3002

EXPOSE 3002

WORKDIR /app/packages/inventory-service

CMD ["node", "dist/index.js"]
