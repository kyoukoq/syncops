FROM node:24-bookworm-slim AS build

WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.31.10-alpine@sha256:aceb952b920393b7d0bc7b978927fc283370bea89fb082c6fef0ce18c60f96a9
USER 0
RUN apk upgrade --no-cache
USER 101:101
COPY --from=build /src/dist /usr/share/nginx/html
COPY --from=config nginx-runtime.conf /etc/nginx/nginx.conf
COPY --from=config nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
