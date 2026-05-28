from app.schemas.market import EventDraft, Market, MarketCandidate
from app.services import event_store


def test_event_store_persists_events(tmp_path, monkeypatch) -> None:
    store_path = tmp_path / "events.json"
    monkeypatch.setattr(event_store, "EVENT_STORE_PATH", store_path)
    event_store.EVENT_STORE.clear()

    event = EventDraft(
        id="event-1",
        market=Market(id="market-1", question="Will a test event happen?"),
        model_type="general_event",
        market_probability=0.4,
        operon_probability=0.45,
    )
    event_store.EVENT_STORE[event.id] = event
    event_store.save_events()

    event_store.EVENT_STORE.clear()
    event_store.load_events()

    assert event_store.get_event("event-1") is not None
    assert event_store.get_event("event-1").market.question == "Will a test event happen?"


def test_election_data_sources_expose_missing_integrations() -> None:
    candidate = MarketCandidate(
        market=Market(
            id="market-1",
            question="Will Gavin Newsom win the 2028 Democratic presidential nomination?",
            market_probability=0.24,
        ),
        operon_score=0.7,
        reason="fit=0.7",
        model_type="election_polling",
        category_guess="politics",
        selected_reason="selected",
        resolution_score=0.9,
        evidence_score=0.8,
        liquidity_score=0.95,
    )

    sources = event_store.build_data_sources(
        candidate=candidate,
        observations=[],
        financial_barrier=None,
        diagnostics=None,
    )

    assert any(
        source.name == "Polymarket market price" and source.status == "connected"
        for source in sources
    )
    assert any(
        source.name == "Pollster database" and source.status == "planned"
        for source in sources
    )
