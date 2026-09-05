# Build context is the repo root (Railway: leave Root Directory blank,
# set Dockerfile Path to apps/web/Dockerfile).
FROM node:20-slim AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json* /app/
RUN npm install
COPY apps/web /app
# VITE_API_URL must be set as a build-time variable in Railway (Vite
# inlines env vars at build, not at container start) - the deployed
# backend's public URL, e.g. https://q-resq-api.up.railway.app
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/dist /app/dist
RUN npm install -g serve

# Railway injects PORT at runtime
CMD ["sh", "-c", "npx serve -s dist -l ${PORT:-4173}"]
