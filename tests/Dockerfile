# Verifier image. Runs in its own container: it sees only the paths declared in `artifacts`.
# It recompiles the agent's Java and runs it, so it needs a JDK; it scores the result with the
# standard library, so it needs nothing else. There is no dependency tree to pre-build, the
# tool is written against the Java standard library, so there is no stale-binary problem.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Verifier tooling, pinned. Nothing is installed at trial time.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt && rm -f /tmp/requirements.txt

# test.sh recompiles and runs the agent's program, so agent-authored code executes in this image,
# and this image holds the answer keys. That code runs as `runner`, never root.
RUN useradd --create-home --uid 10001 --shell /bin/bash runner

# Artifact landing directories must exist before Harbor uploads the declared artifacts.
RUN mkdir -p /app/bore/src /app/data /app/out

# /app is runner-owned so the build can write its classes and its output there, but sticky so
# runner cannot rename or delete the root-owned export beside it.
RUN chown -R runner:runner /app \
    && chmod 1755 /app

# The key for the shipped bore, at a path Harbor does not reserve, readable only by root. /tests
# is a runtime mount, so permissions set on it here are ineffective, and the key cannot be
# protected there.
COPY golden /opt/golden
RUN chmod 700 /opt/golden && chmod 600 /opt/golden/*

# The other bore: its export and its key. test.sh stages the export into a fresh directory after
# the build and runs the agent's class on it a second time, which is what proves the figures are
# computed at run time rather than written into the source.
COPY hidden /opt/hidden
RUN chmod -R go-rwx /opt/hidden

# The third bore, staged the same way at run time. Its licence verdict turns on the pump-intake
# clause rather than on the drawdown rate.
COPY third /opt/third
RUN chmod -R go-rwx /opt/third

COPY . /tests/

WORKDIR /app
