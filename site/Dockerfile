# MediaWiki 1.45 plus a system Lua 5.1 for Scribunto (the binaries bundled with
# Scribunto are x86-64 only, so this also makes ARM hosts work).
FROM mediawiki:1.45
RUN apt-get update && apt-get install -y --no-install-recommends lua5.1 && rm -rf /var/lib/apt/lists/*
# MobileFrontend renders the mobile site with the (bundled) Minerva skin, as minecraft.wiki does.
# It isn't bundled with MediaWiki, so it is fetched at a pinned REL1_45 commit.
ARG MOBILEFRONTEND_COMMIT=dc7fca9f9c010008cac431c723449e7030a84674
RUN git clone -q --branch REL1_45 https://github.com/wikimedia/mediawiki-extensions-MobileFrontend.git extensions/MobileFrontend \
	&& git -C extensions/MobileFrontend checkout -q "$MOBILEFRONTEND_COMMIT" \
	&& rm -rf extensions/MobileFrontend/.git
