# Java / Kotlin (JVM)

## Base image choice

- **Build stage**: `eclipse-temurin:21-jdk-jammy` (or whatever LTS — 21, 17, 11). Includes the full JDK.
- **Runtime stage**: `eclipse-temurin:21-jre-jammy` — JRE only, no compiler. Or `eclipse-temurin:21-jre-alpine` for smaller (musl libc, but JVM doesn't care since it runs in its own VM).
- **For minimum size**: `gcr.io/distroless/java21-debian12`.
- **For real minimum**: use `jlink` to build a custom JRE with only the modules your app uses.

## Maven

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- build stage ----
FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /src

# Copy pom.xml first, resolve deps — separate layer for caching
COPY pom.xml ./
COPY .mvn .mvn
COPY mvnw ./
RUN --mount=type=cache,target=/root/.m2 \
    ./mvnw dependency:go-offline -B

COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    ./mvnw package -DskipTests -B

# ---- runtime stage ----
FROM eclipse-temurin:21-jre-jammy AS runtime
WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app app

COPY --from=build --chown=app:app /src/target/*.jar /app/app.jar

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8080/actuator/health || exit 1

# Sensible container JVM flags
ENTRYPOINT ["java", \
  "-XX:+UseContainerSupport", \
  "-XX:MaxRAMPercentage=75.0", \
  "-jar", "/app/app.jar"]
```

Note the JVM flags:
- `-XX:+UseContainerSupport` is default on Java 10+ but stating it explicitly documents intent.
- `-XX:MaxRAMPercentage=75.0` tells the JVM to use 75% of the container's memory limit. Without this, the JVM may either over- or under-allocate.

For Spring Boot apps, the JAR is "fat" (contains all deps). You can do an even more optimized build using the Spring Boot layered JAR:

```dockerfile
RUN java -Djarmode=layertools -jar app.jar extract
# Then COPY each layer separately so changing your code doesn't bust the deps layer
```

## Gradle

```dockerfile
FROM eclipse-temurin:21-jdk-jammy AS build
WORKDIR /src

COPY gradle gradle
COPY gradlew settings.gradle build.gradle ./
RUN --mount=type=cache,target=/root/.gradle \
    ./gradlew dependencies --no-daemon

COPY src ./src
RUN --mount=type=cache,target=/root/.gradle \
    ./gradlew bootJar --no-daemon -x test
```

`--no-daemon` is important inside a build — the Gradle daemon doesn't help when the container is thrown away.

## jlink — minimal custom JRE

For maximum size savings, build a JRE that only includes the modules your app uses:

```dockerfile
FROM eclipse-temurin:21-jdk-jammy AS jre-build
RUN jlink \
    --add-modules java.base,java.logging,java.sql,java.naming,java.management,jdk.unsupported \
    --strip-debug \
    --no-man-pages \
    --no-header-files \
    --compress=2 \
    --output /custom-jre

FROM debian:bookworm-slim AS runtime
COPY --from=jre-build /custom-jre /opt/jre
ENV PATH="/opt/jre/bin:${PATH}"
# ... rest of runtime stage
```

Custom JRE often comes in around 50 MB versus 200+ MB for a full JRE.

To find the modules your app needs: `jdeps --print-module-deps target/app.jar`.

## .dockerignore for Java

```
target
build
.gradle
.idea
*.iml
.mvn/wrapper/maven-wrapper.jar
out
```
