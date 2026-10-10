from uuid import UUID

from questline.integrations.imessage.state import RelayState

TRIP_ID = UUID("6f1c2a8e-4b8f-4a1e-9a43-2f7c1d0b9e11")


def test_missing_file_loads_empty_state(tmp_path):
    state = RelayState.load(tmp_path / "relay.json")
    assert (state.last_rowid, state.chats, state.names) == (0, {}, {})


def test_state_round_trips(tmp_path):
    path = tmp_path / "relay.json"
    state = RelayState(
        last_rowid=42, chats={"iMessage;+;chat1": TRIP_ID}, names={"+15550001111": "Sam"}
    )
    state.save(path)
    assert RelayState.load(path) == state


def test_save_creates_parent_directories_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "nested" / "relay.json"
    RelayState(last_rowid=1).save(path)
    assert [p.name for p in path.parent.iterdir()] == ["relay.json"]
