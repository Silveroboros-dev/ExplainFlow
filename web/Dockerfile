# Stage 1: Build the Next.js app
FROM node:20-alpine AS builder
WORKDIR /app

# Add build-time environment variables
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_RATE_LIMIT_BYPASS_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_RATE_LIMIT_BYPASS_KEY=$NEXT_PUBLIC_RATE_LIMIT_BYPASS_KEY

COPY web/package*.json ./
RUN npm install
COPY web/ .
RUN npm run build

# Stage 2: Serve with Node
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
