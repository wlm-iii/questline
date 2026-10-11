import pytest

from questline.providers.routes import LatLng
from questline.services.polyline import decode, encode, side_spur

# Google's documented example for the encoded polyline algorithm.
GOOGLE_EXAMPLE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
GOOGLE_POINTS = [LatLng(38.5, -120.2), LatLng(40.7, -120.95), LatLng(43.252, -126.453)]


def close(a: LatLng, b: LatLng) -> bool:
    return abs(a.lat - b.lat) < 1e-5 and abs(a.lng - b.lng) < 1e-5


def test_decode_matches_googles_example():
    assert all(close(a, b) for a, b in zip(decode(GOOGLE_EXAMPLE), GOOGLE_POINTS, strict=True))


def test_encode_matches_googles_example():
    assert encode(GOOGLE_POINTS) == GOOGLE_EXAMPLE


@pytest.mark.parametrize("bad", ["", "_p~iF~ps|U_ulL"])
def test_decode_rejects_empty_or_truncated_input(bad):
    with pytest.raises(ValueError):
        decode(bad)


A, B = LatLng(36.0, -121.0), LatLng(36.0, -120.9)
TURN = LatLng(36.0, -120.95)
SIDE = LatLng(36.01, -120.95)


def test_spur_starts_where_the_route_to_the_side_quest_leaves_the_main_road():
    main = encode([A, TURN, B])
    to_side = encode([A, LatLng(36.0, -120.98), TURN, LatLng(36.005, -120.95), SIDE])

    spur = decode(side_spur(to_side, main, SIDE) or "")

    assert close(spur[0], TURN)
    assert close(spur[-1], SIDE)
    assert len(spur) == 3


def test_spur_uses_the_straight_leg_when_the_main_leg_has_no_polyline():
    to_side = encode([A, TURN, LatLng(36.005, -120.95), SIDE])

    spur = decode(side_spur(to_side, None, SIDE, a=A, b=B) or "")

    assert close(spur[0], TURN)
    assert close(spur[-1], SIDE)


def test_no_spur_without_a_route_to_the_side_quest():
    assert side_spur(None, encode([A, B]), SIDE) is None


def test_no_spur_when_the_side_quest_is_on_the_main_road():
    on_road = LatLng(36.0, -120.95)
    assert side_spur(encode([A, on_road]), encode([A, on_road, B]), on_road) is None
