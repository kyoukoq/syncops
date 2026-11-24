FROM node:24-bookworm-slim AS build

WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
USER 0
RUN apk upgrade --no-cache
USER 101:101
COPY --from=build /src/dist /usr/share/nginx/html
COPY --from=config nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
