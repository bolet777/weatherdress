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
    def __init__(self, status, content):
        self.status_code = status
        self.content = content


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
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


def test_live_phrase_replaces_the_fixed_sentence_until_the_feed_is_empty():
    config = {"ticker": {"enabled": True, "text": "Phrase fixe", "url": URL}}
    session = Session([Response(200, ATOM.encode("utf-8"))])
    fetcher = TickerFetcher(URL, session=session)
    assert phrase_for_render(fetcher, config) == "Phrase fixe"
    fetcher.refresh()
    assert phrase_for_render(fetcher, config) == "●  Première nouvelle  ●  Seconde  ●  "
    assert feed_settings({"ticker": {"enabled": False, "url": URL}}) is None


def test_disabled_ticker_does_not_fetch():
    session = Session([AssertionError("réseau")])
    assert start_in_background(
        {"ticker": {"enabled": False, "url": URL}},
        session=session,
    ) is None
    assert session.calls == []
