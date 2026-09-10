# Go

Go is the easiest language to dockerize well — you produce a single static binary and put it in `scratch` or `distroless`. Final images are 5-20 MB.

## Multi-stage pattern

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- build stage ----
FROM golang:1.23.4-bookworm AS build
WORKDIR /src

# Dependency caching: copy go.mod/go.sum first
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Source + build
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux \
    go build -trimpath -ldflags="-s -w" -o /out/app ./cmd/server

# ---- runtime stage ----
FROM gcr.io/distroless/static-debian12:nonroot AS runtime
WORKDIR /app
COPY --from=build /out/app /app/app

USER nonroot:nonroot
EXPOSE 8080

# Distroless has no shell, so the healthcheck must be the binary itself
# or omit HEALTHCHECK and let the orchestrator probe over HTTP.
ENTRYPOINT ["/app/app"]
```

## Key build flags

- **`CGO_ENABLED=0`** — produces a fully static binary with no glibc/musl dependency. Required for `scratch` and `distroless/static`. Skip only if you genuinely need cgo (SQLite, some crypto libs).
- **`-trimpath`** — strips the build machine's filesystem paths from the binary. Smaller, more reproducible, no leaked `/home/user/projects/...` paths.
- **`-ldflags="-s -w"`** — strips the symbol table and DWARF debug info. Cuts binary size roughly in half. Lose this if you need stack traces with line numbers in production.

## Base image choice for runtime

| Image                                    | Size  | Notes                                          |
| ---------------------------------------- | ----- | ---------------------------------------------- |
| `scratch`                                | 0 MB  | Truly empty. Need to COPY CA certs if your app makes HTTPS calls. |
| `gcr.io/distroless/static-debian12`      | ~2 MB | CA certs + `/etc/passwd` included. **Best default.** |
| `gcr.io/distroless/static-debian12:nonroot` | ~2 MB | Same, with a `nonroot` user already set up. **Recommended.** |
| `alpine:3.20`                            | ~7 MB | Has a shell. Useful if you need to `exec` in to debug. |

For HTTPS calls from `scratch`:

```dockerfile
FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build /out/app /app
ENTRYPOINT ["/app"]
```

## Healthchecks on distroless

Distroless has no shell or `curl`. Three options:

1. **Build a healthcheck endpoint into your binary** and call it via the same binary:
   ```dockerfile
   HEALTHCHECK --interval=30s --timeout=3s CMD ["/app/app", "healthcheck"]
   ```
2. **Use `grpc_health_probe`** for gRPC services — copy the binary into the image.
3. **Skip `HEALTHCHECK` and let Kubernetes/ECS do the HTTP probe** from outside.

## When to use cgo

If you genuinely need `CGO_ENABLED=1` (e.g. `mattn/go-sqlite3`), you can't use `scratch` or `distroless/static`. Options:

- `gcr.io/distroless/base-debian12` — has glibc, still tiny.
- Build with musl for a static cgo binary: more complex, see the Rust reference for the same idea.

## .dockerignore for Go

```
bin
vendor
*.test
*.out
coverage.txt
.air.toml
tmp
```

(Keep `vendor` ignored only if you don't actually commit it. If you do, drop that line.)
