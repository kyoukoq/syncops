FROM node:24-bookworm-slim AS build

WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY --from=config nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
