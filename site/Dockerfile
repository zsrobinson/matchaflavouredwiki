# MediaWiki 1.45 plus a system Lua 5.1 for Scribunto (the binaries bundled with
# Scribunto are x86-64 only, so this also makes ARM hosts work).
FROM mediawiki:1.45
RUN apt-get update && apt-get install -y --no-install-recommends lua5.1 && rm -rf /var/lib/apt/lists/*
