import pytest

from questline.integrations.imessage.commands import (
    Add,
    Build,
    Help,
    Link,
    SetName,
    Unlink,
    parse_command,
)

TRIP_ID = "abc123-Xy_9"


@pytest.mark.parametrize(
    "text", ["", "let's go to big sur", "email me @questline later", "@questlinebot link"]
)
def test_ordinary_text_is_not_a_command(text):
    assert parse_command(text) is None


def test_link_with_trip_id():
    assert parse_command(f"@questline link {TRIP_ID}") == Link(trip_id=TRIP_ID)


def test_prefix_and_verb_are_case_insensitive_and_whitespace_tolerant():
    assert parse_command(f"  @Questline   LINK   {TRIP_ID} ") == Link(trip_id=TRIP_ID)


def test_link_without_id_asks_for_the_trip_link():
    assert parse_command("@questline link") == Link(trip_id=None)


@pytest.mark.parametrize("trip_id", ["abc/123", "a" * 65, "two words"])
def test_link_with_malformed_id_is_help(trip_id):
    assert parse_command(f"@questline link {trip_id}") == Help()


def test_unlink():
    assert parse_command("@questline unlink") == Unlink()


@pytest.mark.parametrize("preset", ["shoestring", "comfortable", "treat"])
def test_build_with_preset(preset):
    assert parse_command(f"@questline build {preset.upper()}") == Build(preset=preset)


def test_build_without_preset():
    assert parse_command("@questline build") == Build(preset=None)


def test_build_with_unknown_preset_is_help():
    assert parse_command("@questline build fancy") == Help()


def test_add_keeps_the_query_text():
    assert parse_command("@questline add  Nepenthe, Big Sur ") == Add(query="Nepenthe, Big Sur")


def test_add_without_query_is_help():
    assert parse_command("@questline add") == Help()


@pytest.mark.parametrize("text", ["@questline I'm Sam Lee", "@questline i’m Sam Lee"])
def test_set_name_accepts_straight_and_curly_apostrophes(text):
    assert parse_command(text) == SetName(name="Sam Lee")


def test_set_name_rejects_names_over_60_characters():
    assert parse_command("@questline I'm " + "x" * 61) == Help()


@pytest.mark.parametrize("text", ["@questline", "@questline what's the plan?"])
def test_anything_else_is_help(text):
    assert parse_command(text) == Help()


def test_verb_may_be_followed_by_a_newline():
    assert parse_command("@questline add\nNepenthe") == Add(query="Nepenthe")
