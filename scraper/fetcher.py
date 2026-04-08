"""
scraper/fetcher.py
HTTP fetching layer with retry logic, exponential backoff, and session reuse.
"""
import logging
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import SSLError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    SCRAPER_DEFAULT_HEADERS,
    SCRAPER_RETRIES,
    SCRAPER_TIMEOUT,
    SCRAPER_DELAY,
    SCRAPER_VERIFY_SSL,
    SCRAPER_ALLOW_INSECURE_SSL_FALLBACK,
    SCRAPER_CA_BUNDLE,
)

log = logging.getLogger(__name__)


def _build_session(retries: int = SCRAPER_RETRIES) -> requests.Session:
    """
    Build a requests.Session with a mounted HTTPAdapter that handles
    low-level connection retries (network errors, 5xx, etc.).
    """
    session = requests.Session()
    session.headers.update(SCRAPER_DEFAULT_HEADERS)

    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# Module-level session (reused across calls for connection pooling)
_session: Optional[requests.Session] = None


def get_session(retries: int = SCRAPER_RETRIES) -> requests.Session:
    global _session
    if _session is None:
        _session = _build_session(retries)
    return _session


def reset_session() -> None:
    """Force a new session to be created (e.g. after auth changes)."""
    global _session
    _session = None


def fetch_url(
    url: str,
    timeout: int = SCRAPER_TIMEOUT,
    delay: float = SCRAPER_DELAY,
    extra_headers: Optional[dict] = None,
    allow_redirects: bool = True,
) -> requests.Response:
    """
    Fetch a single URL and return the Response object.

    Args:
        url:             Full URL including scheme.
        timeout:         Request timeout in seconds.
        delay:           Polite delay to sleep BEFORE the request.
        extra_headers:   Any additional headers to merge in.
        allow_redirects: Follow HTTP redirects.

    Returns:
        requests.Response with r.text / r.content populated.

    Raises:
        requests.HTTPError:    Non-2xx status after all retries.
        requests.RequestException: Connection / timeout failure.
        ValueError:            Malformed or unsafe URL.
    """
    _validate_url(url)

    if delay > 0:
        log.debug(f"Polite delay: sleeping {delay}s before {url}")
        time.sleep(delay)

    session = get_session()
    headers = dict(session.headers)
    if extra_headers:
        headers.update(extra_headers)

    log.info(f"GET {url}")

    # Determine TLS verification behavior.
    # - If SCRAPER_CA_BUNDLE is set, use it as requests' verify path.
    # - Otherwise use SCRAPER_VERIFY_SSL boolean.
    verify: object = SCRAPER_CA_BUNDLE if SCRAPER_CA_BUNDLE else SCRAPER_VERIFY_SSL

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=verify,
        )
    except SSLError as e:
        # In some locked-down environments the CA chain can be misconfigured.
        # We do a single optional fallback retry with verify=False.
        if not SCRAPER_ALLOW_INSECURE_SSL_FALLBACK:
            raise

        log.warning(
            f"SSL verification failed; retrying with verify=False. Error: {e}"
        )
        # Disable warnings only for this fallback attempt.
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=False,
        )
    response.raise_for_status()

    log.debug(
        f"Response: {response.status_code}  "
        f"content-type={response.headers.get('content-type', '?')}  "
        f"size={len(response.content)} bytes"
    )
    return response


def fetch_html(url: str, **kwargs) -> str:
    """Convenience wrapper — returns response text (decoded HTML)."""
    return fetch_url(url, **kwargs).text


def fetch_binary(url: str, **kwargs) -> bytes:
    """Convenience wrapper — returns raw bytes (for PDFs, images, etc.)."""
    return fetch_url(url, **kwargs).content


def _validate_url(url: str) -> None:
    """Basic sanity check to reject obviously malformed URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http/https are supported."
        )
    if not parsed.netloc:
        raise ValueError(f"URL has no host: {url!r}")
