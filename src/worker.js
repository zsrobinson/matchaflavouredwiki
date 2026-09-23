// Redirects every non-canonical hostname to https://matchaflavo.red (same path and query);
// everything else is served from the static assets in dist/.
const CANONICAL = "matchaflavo.red";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname !== CANONICAL && !url.hostname.endsWith(".workers.dev") && url.hostname !== "localhost") {
      url.protocol = "https:";
      url.hostname = CANONICAL;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
