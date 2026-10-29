Harden the `Dockerfile` for production:
- pin the base image to `python:3.12-slim` (no `latest`);
- do not download anything with `ADD <url>`: the repository already contains `scripts/healthcheck.sh`, so copy that
  instead and make it executable;
- install requirements without the pip cache, before copying the rest of the source (for layer caching);
- run as a non-root user named `app` with UID 10001;
- add a `HEALTHCHECK` that runs the health-check script;
- use the exec (JSON array) form for `CMD`.
Keep `EXPOSE 8000` and `WORKDIR /app`. Checked statically; nothing is built.
