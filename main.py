#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import string
import hashlib
import time
import random
import urllib.parse
import sys
import io
from typing import List, Tuple, Dict

if sys.platform == "win32":
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        if sys.stderr.encoding != "utf-8":
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
    except Exception:
        pass

_RNG = random.Random()


def _htok(nbytes: int = 4) -> str:
    return "%0*x" % (nbytes * 2, _RNG.getrandbits(nbytes * 8))


PARAM_POOL = [
    "rand", "junk", "token", "sessionID", "ts", "id",
    "ref", "cb", "ver", "lang", "nocache", "opt",
    "mode", "extra", "session", "flag",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format",
    "device_id", "campaign_id", "user_id", "client_id",
    "visitor_id", "session_id", "tracker", "click_id",
    "ad_id", "source", "medium", "campaign", "content",
    "email_id", "list_id", "segment", "channel",
    "click_token", "conversion_id", "funnel_id", "journey_id",
    "v", "t", "r", "s", "p", "k", "x", "q", "n", "m",
    "d", "c", "f", "g", "h", "j", "w", "z", "a", "b",
    "timestamp", "nonce", "cachebreaker", "_", "time",
    "_t", "_r", "_ts", "_cb", "_nc",
    "no_cache", "fresh", "reload", "bust", "rnd_ts",
    "uid", "hash", "sig", "sign", "secret", "key",
    "page_id", "post_id", "article_id", "product_id",
    "category_id", "tag_id", "author_id",
    "nl_id", "mail_id", "subscriber_id", "cid",
    "gclid", "fbclid", "msclkid", "dclid", "twclid",
    "li_fat_id", "ttclid", "sclid", "wbraid", "gbraid",
    "rnd", "ck", "crc", "chk", "seed", "salt",
    "trace", "flow", "batch", "seq", "idx", "pos",
    "view", "action", "event", "type", "format",
    "quality", "priority", "level", "depth", "offset",
    "screen", "viewport", "dpr", "lang_pref", "tz",
    "referrer_id", "landing", "exit_page", "bounce",
    "scroll_depth", "time_on_page", "interaction",
    "recipient", "template_id", "send_id", "batch_id",
    "variation", "ab_test", "control_group", "cohort",
    "open_tracker", "pixel_id", "beacon", "delivery_id",
    "item_id", "sku", "variant_id", "cart_id",
    "order_id", "checkout_step", "coupon_code",
    "price_id", "plan_id", "tier",
    "share_id", "social_source", "referral_code",
    "invite_code", "promo", "affiliate_id", "partner_id",
    "noop", "void", "null", "tmp", "test",
    "debug", "internal", "preview", "draft",
    "sandbox", "staging", "env", "build",
    "revision", "commit", "deploy_id", "release",
    "fingerprint", "device_hash", "browser_id", "tab_id",
    "window_id", "frame_id", "context", "scope",
    "tenant", "workspace", "project_id", "org_id",
    "team_id", "group_id", "role", "permissions",
    "locale", "region", "country", "city",
    "platform", "os", "browser", "engine",
    "connection_id", "request_id", "correlation_id", "span_id",
    "trace_id", "parent_id", "root_id",
    "xid", "yid", "zid", "kid", "mid", "tid", "pid",
    "rid", "sid", "vid", "wid", "eid", "fid", "gid",
    "hid", "bid", "aid", "did", "lid", "uid2", "cid2",
    "tk", "tn", "tp", "tq", "tr2", "ts2", "tv", "tw", "tx",
]

VALUE_TYPES = [
    "hex4", "hex6", "hex8", "hex12", "hex16", "hex32",
    "hex_upper4", "hex_upper8", "hex_upper16",
    "hex_mixed",
    "digits3", "digits5", "digits8", "digits10",
    "base64_short", "base64_medium", "base64_long",
    "uuid_short", "uuid_full",
    "timestamp_hex", "timestamp_ms", "timestamp_sec",
    "md5", "sha1_short", "sha256_short",
    "float4", "float6",
    "alpha4", "alpha6", "alpha8",
    "alnum6", "alnum10", "alnum16",
    "word",
]


BRAND_WRAPPERS = {
    "google_amp": {
        "type": "direct",
        "verified": True,
        "desc": "Google AMP (cdn.ampproject.org) — client-side редирект на origin (AMP Cache отключён Google 01.07.2026, раньше проксировал)",
        "builder": "_build_google_amp",
    },
    "doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "DoubleClick (adclick.g.doubleclick.net) — рекламный 302-редирект Google",
        "builder": "_build_doubleclick",
    },
    "googleads_doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "GoogleAds DoubleClick (googleads.g.doubleclick.net) — рекламный 302-редирект Google",
        "builder": "_build_googleads_doubleclick",
    },
    "pagead2": {
        "type": "direct",
        "verified": True,
        "desc": "Google Syndication (pagead2.googlesyndication.com) — рекламный 302-редирект Google",
        "builder": "_build_pagead2",
    },
    "ad_doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "DoubleClick Ad (ad.doubleclick.net) — рекламный 302-редирект Google",
        "builder": "_build_ad_doubleclick",
    },
    "tradedesk": {
        "type": "direct",
        "verified": True,
        "desc": "The Trade Desk (insight.adsrvr.org) — рекламный 302-редирект",
        "builder": "_build_tradedesk",
    },
    "fls_doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "DoubleClick FLS (fls.doubleclick.net) — 302-редирект Google",
        "builder": "_build_fls_doubleclick",
    },
    "pubads_doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "DoubleClick PubAds (pubads.g.doubleclick.net) — 302-редирект Google",
        "builder": "_build_pubads_doubleclick",
    },
    "securepubads_doubleclick": {
        "type": "direct",
        "verified": True,
        "desc": "DoubleClick SecurePubAds (securepubads.g.doubleclick.net) — 302-редирект Google",
        "builder": "_build_securepubads_doubleclick",
    },
    "xandr": {
        "type": "direct",
        "verified": True,
        "desc": "Xandr/AppNexus (ib.adnxs.com) — рекламный 307-редирект Microsoft",
        "builder": "_build_xandr",
    },
}

WRAPPER_NAMES = list(BRAND_WRAPPERS.keys())


def _rh(n: int = 8) -> str:
    return _htok(n // 2 + 1)[:n]

def _rs(n: int = 8, chars: str = None) -> str:
    if chars is None:
        chars = string.ascii_lowercase + string.digits
    return ''.join(_RNG.choice(chars) for _ in range(n))

def _rv(vtype: str = None) -> str:
    if vtype is None:
        vtype = _RNG.choice(VALUE_TYPES)

    m = {
        "hex4": lambda: _htok(2),
        "hex6": lambda: _htok(3),
        "hex8": lambda: _htok(4),
        "hex12": lambda: _htok(6),
        "hex16": lambda: _htok(8),
        "hex32": lambda: _htok(16),
        "hex_upper4": lambda: _htok(2).upper(),
        "hex_upper8": lambda: _htok(4).upper(),
        "hex_upper16": lambda: _htok(8).upper(),
        "hex_mixed": lambda: ''.join(c.upper() if _RNG.random() < 0.5 else c for c in _htok(4)),
        "digits3": lambda: str(_RNG.randint(100, 999)),
        "digits5": lambda: str(_RNG.randint(10000, 99999)),
        "digits8": lambda: str(_RNG.randint(10000000, 99999999)),
        "digits10": lambda: str(_RNG.randint(1000000000, 9999999999)),
        "base64_short": lambda: _rs(6, string.ascii_letters + string.digits + "-_"),
        "base64_medium": lambda: _rs(_RNG.randint(10, 20), string.ascii_letters + string.digits + "-_"),
        "base64_long": lambda: _rs(_RNG.randint(20, 40), string.ascii_letters + string.digits + "-_"),
        "uuid_short": lambda: f"{_htok(4)}-{_htok(2)}-{_htok(2)}-{_htok(3)}",
        "uuid_full": lambda: f"{_htok(4)}-{_htok(2)}-4{_rh(3)}-{_RNG.choice('89ab')}{_rh(3)}-{_htok(6)}",
        "timestamp_hex": lambda: hex(int(time.time()) + _RNG.randint(-600, 600))[2:],
        "timestamp_ms": lambda: str(int(time.time() * 1000) + _RNG.randint(-10000, 10000)),
        "timestamp_sec": lambda: str(int(time.time()) + _RNG.randint(-1800, 1800)),
        "md5": lambda: hashlib.md5(_rs(12).encode()).hexdigest(),
        "sha1_short": lambda: hashlib.sha1(_rs(12).encode()).hexdigest()[:16],
        "sha256_short": lambda: hashlib.sha256(_rs(12).encode()).hexdigest()[:20],
        "float4": lambda: f"{_RNG.random():.4f}",
        "float6": lambda: f"{_RNG.random():.6f}",
        "alpha4": lambda: _rs(4, string.ascii_lowercase),
        "alpha6": lambda: _rs(6, string.ascii_lowercase),
        "alpha8": lambda: _rs(8, string.ascii_lowercase),
        "alnum6": lambda: _rs(6, string.ascii_letters + string.digits),
        "alnum10": lambda: _rs(10, string.ascii_letters + string.digits),
        "alnum16": lambda: _rs(16, string.ascii_letters + string.digits),
        "word": lambda: _rs(_RNG.randint(4, 10), string.ascii_lowercase),
    }
    return m.get(vtype, lambda: _htok(4))()


def _case_mix(text: str, prob: float = 0.4) -> str:
    return ''.join(
        (c.upper() if _RNG.random() < 0.5 else c.lower()) if c.isalpha() and _RNG.random() < prob else c
        for c in text
    )


def _param_val(name: str) -> str:
    n = name.lower().replace("_", "").replace("-", "")
    if n in ("ts", "timestamp", "time", "t", "ts2"):
        return str(int(time.time()) + _RNG.randint(-7200, 7200))
    if n in ("", "cachebreaker", "nonce", "fresh", "reload", "nocache", "cb", "ck", "crc",
             "chk", "bust", "rndts", "nc"):
        return str(int(time.time() * 1000) + _RNG.randint(-30000, 30000))
    if n in ("hash", "sig", "sign", "secret", "key", "token", "h", "usg", "salt",
             "seed", "fingerprint", "devicehash"):
        return _htok(_RNG.randint(6, 20))
    if n in ("uid", "uuid", "clientid", "deviceid", "sessionid", "visitorid",
             "userid", "session", "browserid", "tabid", "windowid", "frameid",
             "connectionid", "requestid", "correlationid", "spanid", "traceid",
             "parentid", "rootid"):
        return _rv("uuid_full")
    if n in ("id", "pageid", "postid", "articleid", "productid", "categoryid",
             "tagid", "authorid", "nlid", "mailid", "subscriberid", "cid",
             "clickid", "adid", "emailid", "listid", "segment", "seq",
             "idx", "pos", "batch", "offset", "depth", "templateid", "sendid",
             "batchid", "deliveryid", "pixelid", "itemid", "variantid",
             "cartid", "orderid", "priceid", "planid", "shareid",
             "conversionid", "funnelid", "journeyid", "deployid",
             "projectid", "orgid", "teamid", "groupid",
             "xid", "yid", "zid", "kid", "mid", "tid", "pid",
             "rid", "sid", "vid", "wid", "eid", "fid", "gid",
             "hid", "bid", "aid", "did", "lid", "uid2", "cid2"):
        return str(_RNG.randint(10000, 9999999))
    if n in ("ref", "source", "medium", "campaign", "content", "channel",
             "socialsource", "landing"):
        return _RNG.choice(["email", "newsletter", "direct", "social", "facebook",
                            "twitter", "google", "paid", "organic", "referral",
                            "banner", "sms", "push", "whatsapp", "telegram",
                            "linkedin", "tiktok", "reddit", "pinterest",
                            "youtube", "instagram", "snapchat", "threads",
                            "discord", "slack", "signal", "rss", "blog",
                            "podcast", "webinar", "conference", "press",
                            "partner", "affiliate", "influencer", "retarget"])
    if n in ("ver", "v"):
        return f"{_RNG.randint(1, 9)}.{_RNG.randint(0, 99)}.{_RNG.randint(0, 999)}"
    if n in ("lang", "locale", "langpref", "region", "country"):
        return _RNG.choice(["en", "en-US", "en-GB", "ru", "ru-RU", "de", "de-DE",
                            "fr", "fr-FR", "es", "es-ES", "it", "pt", "pt-BR",
                            "pl", "uk", "tr", "nl", "sv", "da", "no", "fi",
                            "ja", "ko", "zh", "zh-TW", "ar", "hi", "th", "vi"])
    if n in ("nocache", "no_cache", "flag", "opt", "bounce",
             "debug", "preview", "draft", "sandbox", "staging"):
        return str(_RNG.randint(0, 1))
    if n in ("rand", "rnd", "junk", "extra", "r", "s", "p", "k", "x",
             "trace", "flow", "noop", "void", "null", "tmp", "test",
             "q", "n", "m", "d", "c", "f", "g", "j", "w", "z", "a", "b"):
        return _rv()
    if n in ("mode", "action", "event", "type", "view", "format",
             "role", "scope", "context", "tier", "env"):
        return _RNG.choice(["view", "click", "open", "track", "load",
                            "default", "main", "alt", "primary", "secondary",
                            "read", "write", "admin", "user", "guest",
                            "prod", "dev", "test", "beta", "alpha"])
    if n in ("quality", "priority", "level", "scrolldepth",
             "timeonpage", "checkoutstep", "dpr", "screen"):
        return str(_RNG.randint(1, 100))
    if n in ("gclid", "fbclid", "msclkid", "dclid", "twclid",
             "lifatid", "ttclid", "sclid", "wbraid", "gbraid",
             "clicktoken"):
        return _rv("base64_long")
    if n in ("couponcode", "promo", "referralcode", "invitecode",
             "affiliateid", "partnerid"):
        return _rs(_RNG.randint(6, 12), string.ascii_uppercase + string.digits)
    if n in ("platform", "os", "browser", "engine"):
        return _RNG.choice(["windows", "macos", "linux", "ios", "android",
                            "chrome", "firefox", "safari", "edge", "opera"])
    if n in ("tz", "timezone"):
        return _RNG.choice(["UTC", "EST", "PST", "CET", "JST", "IST", "GMT",
                            "MSK", "CST", "AEST", "BRT", "KST"])
    if n in ("variation", "abtest", "controlgroup", "cohort"):
        return _RNG.choice(["A", "B", "C", "D", "control", "variant1", "variant2"])
    if n in ("build", "revision", "commit", "release"):
        return _rv(_RNG.choice(["hex8", "hex12", "digits5"]))
    if n in ("viewport",):
        return _RNG.choice(["1920x1080", "1366x768", "1440x900", "375x812", "414x896"])
    if n in ("interaction",):
        return _RNG.choice(["scroll", "click", "hover", "swipe", "tap", "focus"])

    return _rv()


def _build_google_amp(target_url: str) -> str:
    parsed = urllib.parse.urlparse(target_url)
    host = parsed.hostname or parsed.netloc
    amp_domain = host.replace("-", "--").replace(".", "-")
    path = parsed.path or "/"

    prefix = "/c/s/" if parsed.scheme == "https" else "/c/"
    amp_path = f"{prefix}{parsed.netloc}{path}"
    if parsed.query:
        amp_path += f"?{parsed.query}"

    url = f"https://{amp_domain}.cdn.ampproject.org{amp_path}"
    if parsed.fragment:
        url += f"#{parsed.fragment}"
    return url


def _build_doubleclick(target_url: str) -> str:
    xai = _rs(8, string.ascii_lowercase + string.digits)
    encoded = urllib.parse.quote(target_url, safe='')
    return f"https://adclick.g.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_googleads_doubleclick(target_url: str) -> str:
    xai = _rs(8, string.ascii_lowercase + string.digits)
    encoded = urllib.parse.quote(target_url, safe='')
    return f"https://googleads.g.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_pagead2(target_url: str) -> str:
    xai = _rs(8, string.ascii_lowercase + string.digits)
    encoded = urllib.parse.quote(target_url, safe='')
    return f"https://pagead2.googlesyndication.com/pcs/click?adurl={encoded}&xai={xai}"


def _build_ad_doubleclick(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    xai = _rs(8, string.ascii_lowercase + string.digits)
    return f"https://ad.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_tradedesk(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    return f"https://insight.adsrvr.org/track/clk?r={encoded}"


def _build_fls_doubleclick(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    xai = _rs(8, string.ascii_lowercase + string.digits)
    return f"https://fls.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_pubads_doubleclick(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    xai = _rs(8, string.ascii_lowercase + string.digits)
    return f"https://pubads.g.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_securepubads_doubleclick(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    xai = _rs(8, string.ascii_lowercase + string.digits)
    return f"https://securepubads.g.doubleclick.net/pcs/click?adurl={encoded}&xai={xai}"


def _build_xandr(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe='')
    return f"https://ib.adnxs.com/getuid?{encoded}"


_BUILDERS = {
    "_build_google_amp": _build_google_amp,
    "_build_doubleclick": _build_doubleclick,
    "_build_googleads_doubleclick": _build_googleads_doubleclick,
    "_build_pagead2": _build_pagead2,
    "_build_ad_doubleclick": _build_ad_doubleclick,
    "_build_tradedesk": _build_tradedesk,
    "_build_fls_doubleclick": _build_fls_doubleclick,
    "_build_pubads_doubleclick": _build_pubads_doubleclick,
    "_build_securepubads_doubleclick": _build_securepubads_doubleclick,
    "_build_xandr": _build_xandr,
}


def _apply_wrapper(target_url: str, wrapper_name: str = None) -> str:
    if wrapper_name is None:
        wrapper_name = _RNG.choice(WRAPPER_NAMES)

    w = BRAND_WRAPPERS.get(wrapper_name)
    if not w:
        return target_url

    builder = w.get("builder")
    if builder and builder in _BUILDERS:
        return _BUILDERS[builder](target_url)

    return target_url


def _add_params(url: str, count_range: Tuple[int, int], pool: List[str],
                custom: List[str], case_mix: bool, encoding: bool,
                shuffle: bool) -> str:
    parsed = urllib.parse.urlparse(url)
    params = {}

    if parsed.query:
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            params[k] = v

    num = _RNG.randint(count_range[0], count_range[1])
    avail = [p for p in pool if p not in params]
    if avail:
        chosen = _RNG.sample(avail, min(num, len(avail)))
        for pn in chosen:
            pv = _param_val(pn)
            if case_mix and _RNG.random() < 0.3:
                pn = _case_mix(pn)
            params[pn] = pv

    if custom:
        for cp in custom:
            cp = cp.strip()
            if not cp:
                continue
            if '=' in cp:
                key, val = cp.split('=', 1)
                key, val = key.strip(), val.strip()
                if val == '':
                    val = _rv()
            else:
                key, val = cp, ""
            if case_mix and _RNG.random() < 0.3:
                key = _case_mix(key)
            if key not in params:
                params[key] = val

    items = list(params.items())
    if shuffle:
        _RNG.shuffle(items)

    parts = []
    for k, v in items:
        if v == "":
            parts.append(f"{k}=" if _RNG.random() > 0.3 else k)
        else:
            is_macro = isinstance(v, str) and (v.startswith('{') or v.startswith('%%'))
            if is_macro:
                parts.append(f"{k}={v}")
            elif encoding and _RNG.random() < 0.3:
                enc = _RNG.choice(["single", "double", "mixed"])
                ev = _encode_part(str(v), enc)
                parts.append(f"{k}={ev}")
            else:
                parts.append(f"{k}={v}")

    qs = '&'.join(parts)
    return parsed._replace(query=qs).geturl()


def _encode_part(part: str, enc: str = "none") -> str:
    if enc == "single":
        return urllib.parse.quote(part, safe='=&?/:')
    elif enc == "double":
        return urllib.parse.quote(urllib.parse.quote(part, safe='=&?/:'), safe='=&?/:')
    elif enc == "mixed":
        return ''.join(
            urllib.parse.quote(c, safe='') if _RNG.random() < 0.2 and c.isalpha() else c
            for c in part
        )
    return part


def _add_anchor(url: str) -> str:
    base, _, existing = url.partition('#')
    frag = _RNG.choice([
        _rh(_RNG.randint(4, 12)),
        str(_RNG.randint(1, 9999999)),
        f"utm_{_rs(4)}",
        f"ref_{_rs(3)}",
        f"click_{_RNG.randint(1, 99999)}",
        f"s{_RNG.randint(1, 99999)}",
        _rs(_RNG.randint(3, 10)),
        f"t{int(time.time()) % 1000000}",
        f"id{_RNG.randint(100, 99999)}",
        f"v{_RNG.randint(1, 999)}",
        f"{_rs(2)}{_RNG.randint(10, 9999)}",
        f"p{_rh(6)}",
    ])
    if existing:
        return f"{base}#{existing}_{frag}"
    return f"{base}#{frag}"


def _add_subdomain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        return url
    dom = parsed.netloc.removeprefix("www.")
    sub = _RNG.choice([
        f"mail{_RNG.randint(1, 9999)}", f"srv{_RNG.randint(1, 999)}",
        f"node{_RNG.randint(1, 99)}", f"cdn{_RNG.randint(1, 20)}",
        f"web{_RNG.randint(1, 50)}", f"app{_RNG.randint(1, 20)}",
        _rs(_RNG.randint(4, 8), string.ascii_lowercase),
        f"static{_RNG.randint(1, 10)}", f"go{_RNG.randint(1, 200)}",
        f"link{_RNG.randint(1, 100)}", f"m{_RNG.randint(1, 9)}",
        f"api{_RNG.randint(1, 10)}", f"img{_RNG.randint(1, 30)}",
        f"assets{_RNG.randint(1, 10)}", f"media{_RNG.randint(1, 20)}",
        f"edge{_RNG.randint(1, 10)}", f"proxy{_RNG.randint(1, 10)}",
        f"cache{_RNG.randint(1, 10)}", f"lb{_RNG.randint(1, 5)}",
        f"ns{_RNG.randint(1, 5)}", f"mx{_RNG.randint(1, 5)}",
    ])
    return parsed._replace(netloc=f"{sub}.{dom}").geturl()


def _toggle_proto(url: str) -> str:
    if url.startswith("https://") and _RNG.random() < 0.3:
        return url.replace("https://", "http://", 1)
    if url.startswith("http://") and _RNG.random() < 0.3:
        return url.replace("http://", "https://", 1)
    return url


def _trailing_slash(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if not path:
        path = '/'
    if not path.endswith('/') and '.' not in path.split('/')[-1]:
        if _RNG.random() < 0.5:
            path += '/'
    elif path.endswith('/') and path != '/':
        if _RNG.random() < 0.3:
            path = path[:-1]
    return parsed._replace(path=path).geturl()


def _dot_segments(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if not path or path == '/':
        return url
    parts = path.split('/')
    if len(parts) <= 1:
        return url
    tech = _RNG.choice(["dot", "dotdot", "dslash"])
    idx = _RNG.randint(1, len(parts) - 1)
    if tech == "dot":
        parts.insert(idx, '.')
    elif tech == "dotdot":
        fake = _rs(_RNG.randint(3, 8), string.ascii_lowercase)
        parts.insert(idx, '..')
        parts.insert(idx, fake)
    else:
        parts.insert(idx, '')
    return parsed._replace(path='/'.join(parts)).geturl()


def _percent_encode_random(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if not path or len(path) <= 1:
        return url
    new = []
    for c in path:
        if c == '/':
            new.append(c)
        elif c.isalpha() and _RNG.random() < 0.18:
            fmt = f"%{ord(c):02X}" if _RNG.random() < 0.5 else f"%{ord(c):02x}"
            new.append(fmt)
        else:
            new.append(c)
    return parsed._replace(path=''.join(new)).geturl()


def _fake_path(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if path.count('/') > 4:
        return url
    seg = _RNG.choice([
        f"/{_rs(5)}", f"/go/{_rs(6)}", f"/click/{_RNG.randint(1, 99999)}",
        f"/rd/{_htok(4)}", f"/track/{_rs(8)}",
        f"/redirect/{_RNG.randint(1, 99999)}", f"/l/{_rs(6)}",
        f"/out/{_rs(4)}", f"/away/{_rs(6)}", f"/r/{_rs(4)}",
        f"/u/{_htok(3)}", f"/c/{_rs(5)}",
        f"/t/{_rh(6)}", f"/e/{_rs(4)}", f"/x/{_rh(4)}",
    ])
    return parsed._replace(path=seg + (path or '/')).geturl()


CLOUD_SERVICES = [
    "drive.google.com", "docs.google.com", "www.dropbox.com",
    "onedrive.live.com", "app.box.com", "mega.nz",
    "www.mediafire.com", "e.pcloud.link", "www.icloud.com",
    "www.sync.com", "www.4shared.com",
]

def generate_cloud_html(target_url: str, delay: int = 0) -> str:
    import html as _html
    import json as _json
    nonce = _htok(8)
    safe_html = _html.escape(target_url, quote=True)
    safe_js = (
        _json.dumps(target_url)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )
    title = _RNG.choice(["Loading…", "Redirecting…", "Please wait…", "One moment…",
                         "Opening…", "Just a second…", "Document"])
    filler = "".join(_RNG.choice("abcdefghijklmnopqrstuvwxyz0123456789")
                     for _ in range(_RNG.randint(24, 64)))
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="refresh" content="{delay}; url={safe_html}">
<title>{title}</title>
<!-- {nonce} -->
<script>
// {filler}
(function(){{var t={safe_js};
try{{window.location.replace(t)}}catch(e){{window.location.href=t}}}})();
</script>
</head><body>
<p>Redirecting…</p>
<div style="display:none">{filler}</div>
<noscript><a href="{safe_html}">Click here to continue</a></noscript>
</body></html>"""


def uniquify_url(
    target_url: str,
    mode: str = "ready",
    *,
    params_count_range: Tuple[int, int] = (3, 7),
    param_pool: List[str] = None,
    custom_params: List[str] = None,
    custom_tail: str = None,
    domains: List[str] = None,
    use_wrapper: bool = True,
    wrapper_name: str = None,
    wrapper_layers: int = 1,
    use_anchor: bool = True,
    use_case_mix: bool = True,
    use_encoding: bool = True,
    use_shuffle: bool = True,
    use_trailing_slash: bool = True,
    use_subdomain: bool = False,
    use_proto_random: bool = False,
    use_fake_path: bool = False,
    use_dot_segments: bool = False,
    use_percent_random: bool = False,
    spintax_count: int = 50,
    preset: str = None,
) -> str:

    PRESETS = {
        "soft": dict(params_count_range=(1, 2), use_anchor=False, use_wrapper=False,
                     use_subdomain=False, use_case_mix=False, use_encoding=False,
                     use_proto_random=False, use_fake_path=False, use_trailing_slash=False,
                     use_dot_segments=False, use_percent_random=False, use_shuffle=False,
                     wrapper_layers=0),
        "medium": dict(params_count_range=(2, 4), use_anchor=True, use_wrapper=False,
                       use_subdomain=False, use_case_mix=False, use_encoding=True,
                       use_proto_random=False, use_fake_path=False, use_trailing_slash=True,
                       use_dot_segments=False, use_percent_random=False, use_shuffle=True,
                       wrapper_layers=0),
        "aggressive": dict(params_count_range=(3, 6), use_anchor=True, use_wrapper=False,
                           use_subdomain=False, use_case_mix=True, use_encoding=True,
                           use_proto_random=False, use_fake_path=False, use_trailing_slash=True,
                           use_dot_segments=False, use_percent_random=False, use_shuffle=True,
                           wrapper_layers=0),
        "brand": dict(params_count_range=(2, 4), use_anchor=True, use_wrapper=True,
                      use_subdomain=False, use_case_mix=False, use_encoding=False,
                      use_proto_random=False, use_fake_path=False, use_trailing_slash=False,
                      use_dot_segments=False, use_percent_random=False, use_shuffle=True,
                      wrapper_layers=1),
        "stealth": dict(params_count_range=(4, 8), use_anchor=True, use_wrapper=True,
                        use_subdomain=False, use_case_mix=True, use_encoding=True,
                        use_proto_random=False, use_fake_path=False, use_trailing_slash=True,
                        use_dot_segments=False, use_percent_random=False, use_shuffle=True,
                        wrapper_layers=1),
        "paranoid": dict(params_count_range=(5, 10), use_anchor=True, use_wrapper=True,
                         use_subdomain=False, use_case_mix=True, use_encoding=True,
                         use_proto_random=False, use_fake_path=False, use_trailing_slash=True,
                         use_dot_segments=False, use_percent_random=False, use_shuffle=True,
                         wrapper_layers=2),
    }

    if preset and preset in PRESETS:
        p = PRESETS[preset]
        params_count_range = p.get("params_count_range", params_count_range)
        use_anchor = p.get("use_anchor", use_anchor)
        use_wrapper = p.get("use_wrapper", use_wrapper)
        use_subdomain = p.get("use_subdomain", use_subdomain)
        use_case_mix = p.get("use_case_mix", use_case_mix)
        use_encoding = p.get("use_encoding", use_encoding)
        use_proto_random = p.get("use_proto_random", use_proto_random)
        use_fake_path = p.get("use_fake_path", use_fake_path)
        use_trailing_slash = p.get("use_trailing_slash", use_trailing_slash)
        use_dot_segments = p.get("use_dot_segments", use_dot_segments)
        use_percent_random = p.get("use_percent_random", use_percent_random)
        use_shuffle = p.get("use_shuffle", use_shuffle)
        wrapper_layers = p.get("wrapper_layers", wrapper_layers)

    if param_pool is None:
        param_pool = PARAM_POOL

    if not target_url or not target_url.strip():
        raise ValueError("target_url пуст")

    lo, hi = params_count_range
    if lo > hi:
        lo, hi = hi, lo
    params_count_range = (max(0, lo), max(0, hi))

    if "://" not in target_url:
        target_url = "https://" + target_url.lstrip("/")

    parsed = urllib.parse.urlparse(target_url)
    base_scheme = parsed.scheme or "https"
    base_path = parsed.path
    base_query = parsed.query
    base_fragment = parsed.fragment

    clean_domains = None
    if domains:
        clean_domains = []
        for d in domains:
            d = d.strip()
            if "://" in d:
                d = d.split("://", 1)[1]
            d = d.strip("/").strip()
            if d:
                clean_domains.append(d)
        if not clean_domains:
            clean_domains = None

    eff_domain = parsed.netloc

    def _gen() -> str:
        domain = _RNG.choice(clean_domains) if clean_domains else eff_domain
        result = f"{base_scheme}://{domain}{base_path}"
        if base_query:
            result += f"?{base_query}"
        if base_fragment:
            result += f"#{base_fragment}"

        result = _add_params(result, params_count_range, param_pool,
                             custom_params, use_case_mix, use_encoding, use_shuffle)

        if use_trailing_slash:
            result = _trailing_slash(result)

        if use_fake_path and _RNG.random() < 0.35:
            result = _fake_path(result)

        if use_dot_segments and _RNG.random() < 0.35:
            result = _dot_segments(result)

        if use_percent_random and _RNG.random() < 0.45:
            result = _percent_encode_random(result)

        if use_subdomain and _RNG.random() < 0.45:
            result = _add_subdomain(result)

        if use_proto_random:
            result = _toggle_proto(result)

        _REDIRECT_WRAPPERS = [
            "doubleclick", "googleads_doubleclick", "pagead2",
            "ad_doubleclick", "tradedesk",
            "fls_doubleclick", "pubads_doubleclick", "securepubads_doubleclick",
            "xandr",
        ]
        if use_wrapper and wrapper_layers > 0:
            inner_name = wrapper_name if wrapper_name else None
            result = _apply_wrapper(result, inner_name)
            for _ in range(wrapper_layers - 1):
                result = _apply_wrapper(result, _RNG.choice(_REDIRECT_WRAPPERS))

        if use_anchor:
            result = _add_anchor(result)

        if custom_tail:
            result += custom_tail

        return result

    if mode == "ready":
        return _gen()
    elif mode == "spintax":
        variants = set()
        max_att = spintax_count * 5
        att = 0
        while len(variants) < spintax_count and att < max_att:
            variants.add(_gen())
            att += 1
        return "{" + "|".join(variants) + "}"
    else:
        raise ValueError(f"mode = 'ready' | 'spintax', got: '{mode}'")


def generate_cloud_redirect_page(target_url: str) -> str:
    return generate_cloud_html(target_url)

def list_wrappers() -> List[Dict[str, str]]:
    return [
        {"name": k, "type": v["type"], "desc": v.get("desc", ""),
         "verified": v.get("verified", False)}
        for k, v in BRAND_WRAPPERS.items()
    ]


_GEN_BATCH = 2000


def generate_worker(url, params, count, q, stop):
    seen = set()
    batch = []
    made = 0
    attempts = 0
    max_attempts = count * 6 + 100
    try:
        _RNG.seed()
        while made < count and attempts < max_attempts and not stop.is_set():
            link = uniquify_url(url, "ready", **params)
            attempts += 1
            h = hash(link)
            if h in seen:
                continue
            seen.add(h)
            batch.append(link)
            made += 1
            if len(batch) >= _GEN_BATCH:
                q.put(batch)
                batch = []
        if batch:
            q.put(batch)
    finally:
        try:
            q.put(("__done__", attempts))
        except Exception:
            pass


def randomization_strength(
    *,
    params_count_range: Tuple[int, int] = (3, 7),
    use_wrapper: bool = True,
    wrapper_layers: int = 1,
    domains_count: int = 1,
    use_anchor: bool = True,
    use_shuffle: bool = True,
    use_case_mix: bool = True,
    use_encoding: bool = True,
    use_trailing_slash: bool = True,
    has_custom: bool = False,
    **_ignored,
) -> Tuple[int, str]:
    lo, hi = params_count_range
    if lo > hi:
        lo, hi = hi, lo
    eff = max(0, (lo + hi) / 2)

    base = 0.0
    if use_anchor:          base += 7
    if use_shuffle:         base += 7
    if use_case_mix:        base += 6
    if use_encoding:        base += 6
    if use_trailing_slash:  base += 4

    ui = 0.0
    ui += min(eff, 8) / 8 * 22
    if use_wrapper and wrapper_layers > 0:
        ui += 24 + min(max(wrapper_layers - 1, 0), 1) * 4
    ui += min(max(domains_count - 1, 0), 6) * 2
    if has_custom:
        ui += 8

    pct = max(0, min(100, round(base + ui)))
    if pct >= 70:
        label = "ВЫСОКАЯ"
    elif pct >= 40:
        label = "СРЕДНЯЯ"
    else:
        label = "НИЗКАЯ"
    return pct, label


if __name__ == "__main__":
    print("=" * 70)
    print("  FACET  —  Totalnaya unikalizatsiya ssylok")
    print("=" * 70)

    TARGET = "https://example.com/offer"

    print("\n[1] DEFAULT (vse vklyucheno, 1 wrapper direct):")
    print(uniquify_url(TARGET, "ready"))

    print("\n[2] 3 SLOYA obyortok (troynoy redirect):")
    print(uniquify_url(TARGET, "ready", wrapper_layers=3))

    print("\n[3] SPINTAX (10 variantov):")
    print(uniquify_url(TARGET, "spintax", spintax_count=10))

    print("\n[4] Google AMP wrapper:")
    print(uniquify_url(TARGET, "ready", wrapper_name="google_amp"))

    print("\n[5] DoubleClick wrapper:")
    print(uniquify_url(TARGET, "ready", wrapper_name="doubleclick"))

    print("\n[6] S makrosami maylera:")
    print(uniquify_url(TARGET, "ready",
                       custom_params=["email_id={EMAIL}", "sub_id={SUBSCRIBER_ID}"]))

    print("\n[7] Preset PARANOID:")
    print(uniquify_url(TARGET, "ready", preset="paranoid"))

    print("\n[8] Bez obyortok, tolko randomizatsiya:")
    print(uniquify_url(TARGET, "ready", use_wrapper=False, wrapper_layers=0))

    print("\n[9] Vse dostupnye obyortki:")
    for w in list_wrappers():
        status = "VERIFIED" if w["verified"] else "?"
        print(f"  [{w['type']:7s}] [{status:8s}] {w['name']:25s} {w['desc']}")

    print("\n[10] Cloud HTML:")
    html = generate_cloud_redirect_page(TARGET)
    print(f"  {html[:150]}...")
