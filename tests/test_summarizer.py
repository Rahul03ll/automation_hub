import requests


def test_model_fallback_chain_deduplicates_requested_model():
    from pdf_processor.summarizer import _model_fallback_chain

    chain = _model_fallback_chain("gemini-1.5-flash")
    assert chain[0] == "gemini-1.5-flash"
    assert len(chain) == len(set(chain))


def test_summarize_google_falls_back_after_404(monkeypatch):
    from pdf_processor.summarizer import _summarize_google

    class _Resp404:
        status_code = 404

        def raise_for_status(self):
            raise requests.HTTPError("404 Not Found", response=self)

    class _Resp200:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok summary"}]}}]}

    calls = {"count": 0}

    def _fake_post(url, params, json, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            return _Resp404()
        return _Resp200()

    monkeypatch.setattr("pdf_processor.summarizer.requests.post", _fake_post)

    result = _summarize_google("prompt", "missing-model", "k", 256)
    assert result == "ok summary"
    assert calls["count"] >= 2


def test_summarize_google_retries_on_429(monkeypatch):
    from pdf_processor.summarizer import _summarize_google

    class _Resp429:
        status_code = 429
        headers = {"Retry-After": "0"}

        def raise_for_status(self):
            raise requests.HTTPError("429 Too Many Requests", response=self)

    class _Resp200:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "summary after retry"}]}}]}

    calls = {"count": 0}

    def _fake_post(url, params, json, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            return _Resp429()
        return _Resp200()

    monkeypatch.setattr("pdf_processor.summarizer.requests.post", _fake_post)
    monkeypatch.setattr("pdf_processor.summarizer.time.sleep", lambda *_: None)

    result = _summarize_google("prompt", "gemini-2.0-flash", "k", 256)
    assert result == "summary after retry"
    assert calls["count"] >= 2
