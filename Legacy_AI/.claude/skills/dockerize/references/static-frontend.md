# Static Frontend (Vite, CRA, Next.js export, SvelteKit static, etc.)

For frontends that compile down to static HTML/JS/CSS, the runtime image is just nginx serving files.

## Multi-stage pattern

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- build stage ----
FROM node:20.18.1-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .
RUN npm run build
# Output goes to /app/dist (Vite), /app/build (CRA), /app/out (Next.js export), etc.

# ---- runtime stage ----
FROM nginx:1.27-alpine AS runtime

# Custom nginx config (see below)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# nginx:alpine already creates the `nginx` user; the official image expects to
# run as root for port binding, but the worker drops to nginx. That's acceptable.
# For rootless mode use `nginxinc/nginx-unprivileged:1.27-alpine` and EXPOSE 8080.

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

## nginx.conf

A sane default for an SPA (Vite, CRA, etc.) — handles client-side routing by falling back to `index.html`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Long-cache hashed assets (Vite/webpack output filenames with hashes)
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Never cache index.html — must always fetch latest to get new asset hashes
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # gzip for text-y assets
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;
}
```

## Rootless nginx

If your platform requires non-root containers (Kubernetes with restricted PSS, etc.), use the unprivileged image:

```dockerfile
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
```

Note: it listens on 8080, not 80, since non-root can't bind to ports below 1024.

## Build-time env vars (Vite, CRA)

Frontend bundles bake env vars at build time, not runtime. You can't change `VITE_API_URL` by setting an env var on the running container. Options:

1. **Build per environment** (different image for staging vs prod). Simple, slow.
2. **Runtime templating**: bake a placeholder like `__API_URL__` into the bundle, replace at container start via an entrypoint script that does `sed` on the JS files before nginx starts.
3. **Runtime config endpoint**: app fetches `/config.json` at startup; nginx serves a different file based on env. The file can be templated by an entrypoint script.

For Next.js, the situation is different — server components and `NEXT_PUBLIC_*` runtime envs work normally if you're running the Node server (`output: 'standalone'`), not doing a static export.

## .dockerignore additions

```
dist
build
out
.next
.nuxt
.svelte-kit
.vite
.parcel-cache
storybook-static
```
