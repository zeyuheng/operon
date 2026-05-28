from app.schemas.market import EventDraft, Market
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
