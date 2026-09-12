# The hydrogeology team's tooling is Java, so the agent's project is compiled with javac.
# Canonical Python base: the harness runs on it, and nothing here needs a Python numerics stack.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# A headless JDK is the whole toolchain: the tool is written against the Java standard library,
# with no external package, so nothing has to be fetched at solve time on an offline box.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-jdk-headless \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

# The project the agent completes, and the logger exports.
COPY bore /app/bore
COPY data /app/data
RUN chmod +x /app/bore/build.sh && mkdir -p /app/out

WORKDIR /app
