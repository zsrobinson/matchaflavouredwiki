// Canonical hosts, wiki aliases, case variants and HTML/slash variants all use permanent redirects.
import table from "./redirects.json";

const CANONICAL = "matchaflavou.red";
const titles = new Map(Object.entries(table.titles));
const redirects = new Map(Object.entries(table.redirects));
const aliases = new Map(Object.entries(table.redirects).map(([key, value]) => [key.toLowerCase(), value]));

function encodeSegment(segment) {
  try {
    return encodeURIComponent(decodeURIComponent(segment));
  } catch {
    return segment;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const target = new URL(url);
    const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
    const preview = url.hostname.endsWith(".workers.dev");
    if (!local && !preview) {
      target.protocol = "https:";
      target.hostname = CANONICAL;
      target.port = "";
    }
    if (url.pathname.startsWith("/w/")) {
      let key;
      try {
        key = decodeURIComponent(url.pathname.slice(3)).replace(/ /g, "_").replace(/\/$/, "");
      } catch {
        key = url.pathname.slice(3);
      }
      // Only normalize known titles: genuinely missing pages still receive the asset 404.
      let canonical = titles.get(key.toLowerCase());
      let redirect = redirects.get(key) || aliases.get(key.toLowerCase());
      if (!canonical && !redirect && key.endsWith(".html")) {
        key = key.slice(0, -5);
        canonical = titles.get(key.toLowerCase());
        redirect = redirects.get(key) || aliases.get(key.toLowerCase());
      }
      if (redirect) {
        const destination = new URL(redirect, target);
        target.pathname = destination.pathname;
        target.hash = destination.hash;
      } else if (key === "Matcha_Flavoured_Wiki" || canonical === "Matcha_Flavoured_Wiki") {
        target.pathname = "/";
      } else if (canonical) {
        // Match the export's canonical URL encoding, including namespace colons.
        target.pathname = "/w/" + encodeURIComponent(canonical).replace(/%(?:2F|3A|2C|24|40|3B|3D|2B|26)/g, decodeURIComponent);
      }
    }
    if (target.toString() !== url.toString()) {
      return Response.redirect(target.toString(), 301);
    }
    // The asset server 307s any path not in its own encoding (encodeURIComponent per segment,
    // so ":" becomes "%3A"), which loops with the ":" URLs above: hand it that form instead
    const asset = new URL(url);
    asset.pathname = url.pathname.split("/").map(encodeSegment).join("/");
    const response = await env.ASSETS.fetch(new Request(asset, request));
    if (!preview) {
      return response;
    }
    // PR previews and the workers.dev address are copies of the site: keep them out of search
    const headers = new Headers(response.headers);
    headers.set("X-Robots-Tag", "noindex");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  },
};
