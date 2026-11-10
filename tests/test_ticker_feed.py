"""Flux du bandeau : RSS et Atom fictifs. Aucun appel réseau."""

from weatherdress.ticker_feed import (
    TickerFetcher,
    feed_settings,
    normalize_feed_url,
    parse_feed,
    phrase_for_render,
    start_in_background,
)

TOKEN = "SECRET-RSS-TOKEN"
URL = f"https://nouvelles.example.test/{TOKEN}.xml"

RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <item><title>Un &amp; deux</title></item>
    <item><title>  Espaces   multiples </title></item>
    <item><title><![CDATA[Avec <b>gras</b>]]></title></item>
    <item><title>   </title></item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Première nouvelle</title></entry>
  <entry><title>Seconde</title></entry>
</feed>
"""


class Response:
    def __init__(self, status, content, content_type=""):
        self.status_code = status
        self.content = content
        self.headers = {"content-type": content_type} if content_type else {}


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        self.headers.append(headers or {})
        responder = self.responses.pop(0)
        if isinstance(responder, Exception):
            raise responder
        return responder


def test_only_http_and_https_are_accepted():
    assert normalize_feed_url(f"  {URL}  ") == URL
    assert normalize_feed_url("http://nouvelles.example.test/rss") == "http://nouvelles.example.test/rss"
    assert normalize_feed_url("") is None
    assert normalize_feed_url("ftp://nouvelles.example.test/rss") is None
    assert normalize_feed_url(None) is None


def test_empty_address_keeps_the_fixed_sentence(capsys):
    config = {"ticker": {"enabled": True, "text": "Phrase fixe", "url": "  "}}
    assert feed_settings(config) is None
    assert start_in_background(config, session=Session([])) is None
    assert phrase_for_render(None, config) == "Phrase fixe"
    assert TOKEN not in capsys.readouterr().out


def test_refused_address_is_not_printed(capsys):
    config = {"ticker": {"enabled": True, "text": "Phrase fixe", "url": f"file:///{TOKEN}"}}
    assert start_in_background(config) is None
    captured = capsys.readouterr().out
    assert "refusée" in captured
    assert TOKEN not in captured


def test_rss_and_atom_titles_become_one_phrase():
    assert parse_feed(RSS) == "●  Un & deux  ●  Espaces multiples  ●  Avec gras  ●  "
    assert parse_feed(ATOM) == "●  Première nouvelle  ●  Seconde  ●  "
    assert parse_feed(b"<nope") == ""
    assert parse_feed(b"<rss><channel></channel></rss>") == ""


def test_titles_stop_after_twelve():
    items = "".join(f"<item><title>Titre {index}</title></item>" for index in range(1, 20))
    phrase = parse_feed(f"<rss><channel>{items}</channel></rss>")
    assert "Titre 12" in phrase
    assert "Titre 13" not in phrase


def test_failed_fetch_keeps_the_previous_phrase_and_hides_the_address(capsys):
    session = Session([
        Response(200, RSS.encode("utf-8")),
        OSError(f"échec {URL}"),
        Response(503, b""),
    ])
    fetcher = TickerFetcher(URL, session=session)
    fetcher.refresh()
    assert fetcher.snapshot().startswith("●  Un & deux")
    fetcher.refresh()
    fetcher.refresh()
    assert fetcher.snapshot().startswith("●  Un & deux")
    captured = capsys.readouterr().out
    assert TOKEN not in captured
    assert URL not in captured
    assert session.calls == [URL, URL, URL]


def test_configured_feed_hides_the_fixed_sentence_until_titles_arrive():
    config = {"ticker": {"enabled": True, "text": "Phrase fixe", "url": URL}}
    session = Session([Response(200, ATOM.encode("utf-8"))])
    fetcher = TickerFetcher(URL, session=session)
    assert phrase_for_render(fetcher, config) == ""
    assert phrase_for_render(None, config) == ""
    fetcher.refresh()
    assert phrase_for_render(fetcher, config) == "●  Première nouvelle  ●  Seconde  ●  "
    assert feed_settings({"ticker": {"enabled": False, "url": URL}}) is None


def test_request_asks_for_rss_without_the_app_name():
    session = Session([Response(200, RSS.encode("utf-8"))])
    TickerFetcher(URL, session=session).refresh()
    headers = session.headers[0]
    assert "rss+xml" in headers["Accept"]
    assert "WeatherDress" not in headers["User-Agent"]
    assert TOKEN not in headers["User-Agent"]


def test_html_body_is_retried_then_reported_without_the_address(capsys):
    html = b"<html><body>Acces refuse<br>"
    session = Session([
        Response(200, html, "text/html"),
        Response(200, html, "text/html"),
    ])
    fetcher = TickerFetcher(URL, session=session)
    fetcher.refresh()
    assert fetcher.snapshot() == ""
    assert len(session.calls) == 2
    assert "atom+xml" in session.headers[1]["Accept"]
    assert "text/xml" not in session.headers[1]["Accept"]
    captured = capsys.readouterr().out
    assert "corps illisible" in captured
    assert "HTTP 200" in captured
    assert "text/html" in captured
    assert TOKEN not in captured
    assert URL not in captured


def test_disabled_ticker_does_not_fetch():
    session = Session([AssertionError("réseau")])
    assert start_in_background(
        {"ticker": {"enabled": False, "url": URL}},
        session=session,
    ) is None
    assert session.calls == []
