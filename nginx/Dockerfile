# syntax=docker/dockerfile:1.7

# Builds the React app and serves it with nginx. The frontend source comes from
# the `frontend` build context (see compose.yaml), so nginx/ stays the context root.

FROM node:26-alpine AS build
WORKDIR /app
COPY --from=frontend package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY --from=frontend . .
RUN npm run build

FROM nginx:1.30-alpine
COPY default.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
