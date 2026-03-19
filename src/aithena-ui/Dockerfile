ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# ---------- build stage ----------
FROM node:22-alpine AS build

ARG VERSION

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV VERSION=${VERSION}
RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine AS runtime

ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/jmservera/aithena" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE}

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/

EXPOSE 80
