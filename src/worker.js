// Serves the static wiki from dist/ (ASSETS). In front of it:
//  - every alternate hostname 301-redirects to https://matchaflavou.red (same path and query);
//  - wiki redirects (e.g. /w/Emerald -> /w/Obol) and wrong-case titles (/w/mud_kiln -> /w/Mud_Kiln)
//    are real 301s, from src/redirects.json written by tools/export_static.py (tools/seo.py);
//  - phones get the mobile site (MobileFrontend + Minerva, as on minecraft.wiki) at the same URL,
//    from dist/mobile/. The footer's "Mobile view" / "Desktop" links (?mobileaction=toggle_view_*)
//    override the user-agent guess with MobileFrontend's cookies.
import table from "./redirects.json";

const CANONICAL = "matchaflavou.red";
// MobileFrontend's rule of thumb: phones and tablets that say so get the mobile view
const MOBILE_UA = /Mobi|Android|iPhone|iPod|iPad|Opera Mini|IEMobile|BlackBerry|webOS|Kindle|Silk/i;
const COOKIE_MOBILE = "mf_useformat";
const COOKIE_DESKTOP = "stopMobileRedirect";

function location(url, path) {
  const target = new URL(path, url);
  target.search = url.search;
  return target.toString();
}

function cookie(request, name) {
  const m = (request.headers.get("Cookie") || "").match(new RegExp("(?:^|;\\s*)" + name + "=([^;]*)"));
  return m ? m[1] : null;
}

function wantsMobile(request) {
  if (cookie(request, COOKIE_DESKTOP) === "true") return false;
  if (cookie(request, COOKIE_MOBILE) === "true") return true;
  return MOBILE_UA.test(request.headers.get("User-Agent") || "");
}

// Pages that exist in both views: the main page, articles and the search page
function isPage(pathname) {
  return pathname === "/" || pathname.startsWith("/w/") || pathname === "/search" || pathname.startsWith("/search/");
}

async function servePage(request, env, url) {
  let res;
  if (wantsMobile(request)) {
    const mobile = new URL(url);
    mobile.pathname = "/mobile" + url.pathname;
    res = await env.ASSETS.fetch(new Request(mobile, request));
  } else {
    res = await env.ASSETS.fetch(request);
  }
  res = new Response(res.body, res);
  const loc = res.headers.get("Location");
  if (loc) {
    // trailing-slash redirects from the mobile tree keep the public path
    res.headers.set("Location", loc.replace(/^(https?:\/\/[^/]+)?\/mobile(?=\/)/, "$1"));
  }
  res.headers.append("Vary", "User-Agent, Cookie");
  return res;
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
    // "Mobile view" / "Desktop" footer links: remember the choice, then show the page without the parameter
    const action = url.searchParams.get("mobileaction");
    if (action === "toggle_view_mobile" || action === "toggle_view_desktop") {
      url.searchParams.delete("mobileaction");
      const year = "; Path=/; Max-Age=31536000; SameSite=Lax";
      const headers = new Headers({ Location: url.toString(), "Cache-Control": "no-store" });
      if (action === "toggle_view_mobile") {
        headers.append("Set-Cookie", COOKIE_MOBILE + "=true" + year);
        headers.append("Set-Cookie", COOKIE_DESKTOP + "=; Path=/; Max-Age=0");
      } else {
        headers.append("Set-Cookie", COOKIE_DESKTOP + "=true" + year);
        headers.append("Set-Cookie", COOKIE_MOBILE + "=; Path=/; Max-Age=0");
      }
      return new Response(null, { status: 302, headers });
    }
    // the mobile tree is only reached through the rewrite above
    if (url.pathname === "/mobile" || url.pathname.startsWith("/mobile/")) {
      return Response.redirect(location(url, url.pathname.slice("/mobile".length) || "/"), 301);
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
    if (isPage(url.pathname)) {
      return servePage(request, env, url);
    }
    return env.ASSETS.fetch(request);
  },
};
