"""
utils/affiliate.py
Converts raw product URLs into tagged affiliate links.
Extend AFFILIATE_TAGS / add per-source branches as you onboard more programs.
"""

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

AFFILIATE_TAGS = {
    "amazon": {"param": "tag", "value": "yourtag-20"},
    "aliexpress": {"param": "aff_id", "value": "your_aliexpress_id"},
    # add more sources here, e.g. "rakuten": {"param": "...", "value": "..."}
}


def tag_affiliate_link(raw_url: str, source: str) -> str:
    """
    Append/replace the affiliate query param for a known source.
    Falls back to the raw URL untouched if the source isn't configured yet,
    so a missing mapping never breaks the bot -- it just earns nothing on that link.
    """
    source = source.lower()
    config = AFFILIATE_TAGS.get(source)
    if not config:
        return raw_url

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query))
    query[config["param"]] = config["value"]
    new_query = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
