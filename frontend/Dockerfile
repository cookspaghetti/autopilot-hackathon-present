# --- Base Stage ---
FROM node:20-alpine AS base

WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# --- Dependencies Stage ---
FROM base AS deps
RUN npm ci

# --- Development Stage ---
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]


# --- Production Build Stage ---
FROM deps AS builder
# Accept build arguments for Next.js environment variables
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_BASE_PATH
ARG NEXTAUTH_SECRET
ARG NEXTAUTH_URL
ARG AUTH_DEBUG

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
ENV NEXTAUTH_SECRET=$NEXTAUTH_SECRET
ENV NEXTAUTH_URL=$NEXTAUTH_URL
ENV AUTH_DEBUG=$AUTH_DEBUG

COPY . .
RUN npm run build

# --- Production Stage ---
FROM base AS prod
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json .
COPY --from=builder /app/package-lock.json .
COPY --from=builder /app/next.config.ts .
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "start"]
