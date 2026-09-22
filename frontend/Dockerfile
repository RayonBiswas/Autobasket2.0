# Builds the web app and serves it from Caddy, which is also the public edge (TLS + /api proxy).
FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# In production the app calls the API on the same origin under /api (Caddy proxies it).
ENV VITE_API_URL=/api
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
EXPOSE 80 443
