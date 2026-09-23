// Serves the static wiki from dist/ (ASSETS). In front of it:
//  - every alternate hostname 301-redirects to https://matchaflavou.red (same path and query);
//  - wiki redirects (e.g. /w/Emerald -> /w/Obol) and wrong-case titles (/w/mud_kiln -> /w/Mud_Kiln)
//    are real 301s, from src/redirects.json written by tools/export_static.py (tools/seo.py).
import table from "./redirects.json";

const CANONICAL = "matchaflavou.red";

function location(url, path) {
  const target = new URL(path, url);
  target.search = url.search;
  return target.toString();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname !== CANONICAL && !url.hostname.endsWith(".workers.dev") && url.hostname !== "localhost") {
      url.protocol = "https:";
      url.hostname = CANONICAL;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    if (url.pathname.startsWith("/w/")) {
      let key;
      try {
        key = decodeURIComponent(url.pathname.slice(3)).replace(/ /g, "_").replace(/\/$/, "");
      } catch (e) {
        key = url.pathname.slice(3);
      }
      const redirect = table.redirects[key];
      if (redirect) {
        return Response.redirect(location(url, redirect), 301);
      }
      const canonical = table.titles[key.toLowerCase()];
      if (canonical && canonical !== key) {
        return Response.redirect(location(url, "/w/" + encodeURIComponent(canonical).replace(/%2F/g, "/")), 301);
      }
      if (key === "Matcha_Flavoured_Wiki") {
        return Response.redirect(location(url, "/"), 301);
      }
    }
    return env.ASSETS.fetch(request);
  },
};
