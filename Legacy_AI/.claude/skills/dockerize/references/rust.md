# Rust

Rust compile times are long, so dependency caching is *critical*. The naive approach (copy everything, `cargo build`) recompiles every dependency on every source change. Use `cargo-chef` or the manual trick below.

## Pattern 1: cargo-chef (recommended)

`cargo-chef` produces a "recipe" of dependencies that can be cached independently of your source.

```dockerfile
# syntax=docker/dockerfile:1.7

FROM rust:1.83-slim-bookworm AS chef
RUN cargo install cargo-chef --locked
WORKDIR /app

# ---- planner: figure out what deps to build ----
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# ---- builder: build deps first (cached), then source ----
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
RUN cargo build --release --bin myapp

# ---- runtime stage ----
FROM gcr.io/distroless/cc-debian12:nonroot AS runtime
WORKDIR /app
COPY --from=builder /app/target/release/myapp /app/myapp

USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/myapp"]
```

When you change a source file, the `cargo chef cook` layer stays cached — only the final `cargo build` recompiles your code (typically seconds, not minutes).

## Pattern 2: manual trick (no extra tool)

If you don't want a `cargo-chef` dependency:

```dockerfile
FROM rust:1.83-slim-bookworm AS build
WORKDIR /app

# Create a dummy main to compile deps in isolation
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release && rm -rf src target/release/myapp*

# Now copy real source and rebuild — deps layer cached
COPY src ./src
RUN cargo build --release
```

Less clean than cargo-chef but no external dep.

## Static (musl) builds for scratch/distroless-static

By default rust links against glibc. For `scratch` or `distroless/static`, build with musl:

```dockerfile
FROM rust:1.83-slim-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends musl-tools && \
    rustup target add x86_64-unknown-linux-musl
WORKDIR /app
COPY . .
RUN cargo build --release --target x86_64-unknown-linux-musl

FROM gcr.io/distroless/static-debian12:nonroot AS runtime
COPY --from=build /app/target/x86_64-unknown-linux-musl/release/myapp /myapp
USER nonroot:nonroot
ENTRYPOINT ["/myapp"]
```

For ARM (M-series Macs, AWS Graviton), substitute `aarch64-unknown-linux-musl`. Or build multi-arch with buildx.

## Runtime base image choice

| Image                                    | When                                          |
| ---------------------------------------- | --------------------------------------------- |
| `gcr.io/distroless/cc-debian12:nonroot`  | Default — for glibc binaries (no musl needed). |
| `gcr.io/distroless/static-debian12:nonroot` | For musl static binaries.                  |
| `scratch`                                | For musl static binaries, if you also COPY CA certs. |
| `debian:bookworm-slim`                   | If you need a shell to debug.                 |

## .dockerignore for Rust

```
target
Cargo.lock.bak
**/*.rs.bk
```

(Don't ignore `Cargo.lock` for binaries — you want it in the image's build context.)
