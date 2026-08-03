"""The three games, and the geography they rest on."""
from datetime import datetime, timedelta, timezone

import pytest

from radiorumble import adif, dxcc, maidenhead
from radiorumble.config import Contest, Team
from radiorumble.modes import REJECT_DOMESTIC, REJECT_NOT_US, build
from radiorumble.scoring import Scoreboard

NOW = datetime(2026, 9, 12, 18, 30, tzinfo=timezone.utc)

# Squares chosen so each sits unambiguously in one state.
GRID_STATES = {
    "EM19": ("Kansas",),
    "EM28": ("Kansas", "Missouri"),      # a square straddling a border
    "EN52": ("Wisconsin",),
    "DM79": ("Colorado",),
    "JO41": (),                          # Germany: no US state
}


def make_contest(mode="classic", settings=None, **overrides):
    defaults = dict(
        name="Test Rumble",
        start=NOW - timedelta(hours=1),
        end=NOW + timedelta(hours=1),
        bands=frozenset({"20m", "40m"}),
        modes=frozenset({"FT8"}),
        qso_points=1,
        dupe_scope="band",
        teams=(
            Team("Kansas State", "KSU", "#512888", ("KE0VUM",)),
            Team("Kansas", "KU", "#0051BA", ("KD2FMW",)),
        ),
        log_file=None,
        grid_states=GRID_STATES,
        mode=mode,
        mode_settings=settings or {},
    )
    defaults.update(overrides)
    return Contest(**defaults)


def board_for(mode, settings=None, **overrides):
    contest = make_contest(mode, settings, **overrides)
    return Scoreboard(contest, build(mode, settings or {}))


def qso(station="KE0VUM", call="W1ABC", band="20m", mode="FT8", grid="EM19", when=NOW):
    return adif.Qso(station=station, call=call, band=band, mode=mode,
                    grid=grid, my_grid="EM19RF", when=when)


# ===================== maidenhead =====================

def test_a_grid_square_converts_to_the_centre_of_its_box():
    lat, lon = maidenhead.to_latlon("EM19")
    assert (lat, lon) == (39.5, -97.0)


def test_a_six_character_locator_is_more_precise_than_four():
    assert maidenhead.to_latlon("EM19RF") != maidenhead.to_latlon("EM19")


def test_a_position_round_trips_back_to_its_square():
    assert maidenhead.to_square(39.19, -96.58) == "EM19"


def test_nonsense_is_rejected_rather_than_guessed():
    assert maidenhead.to_latlon("") is None
    assert maidenhead.to_latlon("ZZ99") is None
    assert maidenhead.to_latlon("hello") is None


@pytest.mark.parametrize("square,lat,lon", [
    ("BP51", 61.5, -149.0),   # Anchorage
    ("BL11", 21.5, -157.0),   # Honolulu
    ("JO41", 51.5, 9.0),      # central Germany
    ("PM95", 35.5, 139.0),    # Tokyo
])
def test_known_squares_land_in_the_right_place(square, lat, lon):
    got = maidenhead.to_latlon(square)
    assert abs(got[0] - lat) < 0.6 and abs(got[1] - lon) < 1.2


# ===================== dxcc =====================

@pytest.mark.parametrize("call,country,is_dx", [
    ("W1ABC", "United States", False),
    ("KE0VUM", "United States", False),
    ("AA1XY", "United States", False),
    ("VE3ABC", "Canada", True),
    ("G0ABC", "England", True),
    ("JA1XYZ", "Japan", True),
    ("EA8XX", "Canary Islands", True),   # longer prefix beats EA/Spain
    ("EA1XX", "Spain", True),
    ("VP8ABC", "Falkland Islands", True),
])
def test_prefixes_resolve_to_countries(call, country, is_dx):
    assert dxcc.lookup(call)[0] == country
    assert dxcc.is_dx(call) is is_dx


def test_us_territories_are_dx_despite_us_style_callsigns():
    """KH6 and KP4 look domestic but are separate DXCC entities."""
    assert dxcc.lookup("KH6ABC")[0] == "Hawaii"
    assert dxcc.is_dx("KH6ABC") is True
    assert dxcc.is_dx("KL7AA") is True


def test_a_portable_indicator_names_where_the_operator_is():
    """W1ABC/VE3 is a US operator in Canada; the contact is with Canada."""
    assert dxcc.country("W1ABC/VE3") == "Canada"
    assert dxcc.country("VE3/W1ABC") == "Canada"


def test_meaningless_suffixes_do_not_change_the_country():
    """Compared against the bare callsign, not a fixed name — cty.dat's
    official spellings are its own business ("Fed. Rep. of Germany")."""
    assert dxcc.country("K5XYZ/QRP") == "United States"
    assert dxcc.country("DL1ABC/P") == dxcc.country("DL1ABC")
    assert dxcc.country("DL1ABC") != dxcc.UNKNOWN


def test_an_unrecognised_prefix_is_dx_rather_than_dropped():
    """Refusing to score a real contact is worse than an unknown country."""
    country, _, is_dx = dxcc.lookup("1Z9ZZZ")
    assert is_dx is True
    assert country == dxcc.UNKNOWN


# ===================== classic =====================

def test_classic_scores_points_times_squares():
    board = board_for("classic")
    board.add(qso(call="W1ABC", grid="EM19"))
    board.add(qso(call="W2ABC", grid="EN52"))
    assert board.standings()[0]["score"] == 4       # 2 points x 2 squares


# ===================== conquest =====================

def test_working_a_state_claims_it():
    board = board_for("conquest")
    board.add(qso(station="KE0VUM", grid="EM19"))
    assert board.owners["Kansas"] == "KSU"


def test_a_square_straddling_a_border_claims_both_states():
    """FT8 sends a grid and nothing else, so which side of the line is unknowable."""
    board = board_for("conquest")
    board.add(qso(grid="EM28"))
    assert board.owners["Kansas"] == "KSU"
    assert board.owners["Missouri"] == "KSU"


def test_a_contact_outside_the_us_takes_no_territory():
    board = board_for("conquest")
    assert board.add(qso(grid="JO41")) == REJECT_NOT_US
    assert board.owners == {}


def test_under_first_rules_the_second_team_cannot_take_a_state():
    board = board_for("conquest", {"claim": "first"})
    board.add(qso(station="KE0VUM", call="W1ABC", grid="EM19"))
    board.add(qso(station="KD2FMW", call="W2ABC", grid="EM19"))
    board.add(qso(station="KD2FMW", call="W3ABC", grid="EM19"))
    assert board.owners["Kansas"] == "KSU"


def test_under_most_rules_a_state_changes_hands():
    """This is the version that behaves like a game."""
    board = board_for("conquest", {"claim": "most"})
    board.add(qso(station="KE0VUM", call="W1ABC", grid="EM19"))
    assert board.owners["Kansas"] == "KSU"

    board.add(qso(station="KD2FMW", call="W2ABC", grid="EM19"))
    assert board.owners["Kansas"] == "KSU", "a tie is held by whoever claimed it first"

    board.add(qso(station="KD2FMW", call="W3ABC", grid="EM19"))
    assert board.owners["Kansas"] == "KU", "more contacts takes the state"


def test_conquest_score_is_territory_held():
    board = board_for("conquest")
    board.add(qso(station="KE0VUM", call="W1ABC", grid="EM19"))   # Kansas
    board.add(qso(station="KE0VUM", call="W2ABC", grid="EN52"))   # Wisconsin
    board.add(qso(station="KD2FMW", call="W3ABC", grid="DM79"))   # Colorado
    rows = {r["abbr"]: r for r in board.standings()}
    assert rows["KSU"]["score"] == 2
    assert rows["KU"]["score"] == 1
    assert rows["KSU"]["owned"] == ["Kansas", "Wisconsin"]


def test_the_map_payload_carries_owners_and_colours():
    board = board_for("conquest")
    board.add(qso(grid="EM19"))
    payload = board.snapshot()["map"]
    assert payload["owners"]["Kansas"] == "KSU"
    assert payload["colors"]["KSU"] == "#512888"
    assert payload["claim_rule"] == "first"


# ===================== dx =====================

def test_a_domestic_contact_does_not_score_in_dx_mode():
    board = board_for("dx")
    assert board.add(qso(call="W1ABC")) == REJECT_DOMESTIC


def test_a_dx_contact_scores_the_dx_rate():
    board = board_for("dx", {"points_per_dx": 3})
    assert board.add(qso(call="DL1ABC", grid="JO41")) is None
    assert board.teams["KSU"].points == 3


def test_countries_are_the_multiplier_not_grid_squares():
    """Twenty contacts into Germany is one multiplier; twenty countries is twenty."""
    board = board_for("dx")
    board.add(qso(call="DL1ABC", grid="JO41"))
    board.add(qso(call="DL2ABC", grid="JO41"))
    assert board.teams["KSU"].entities == {dxcc.country("DL1ABC")}
    assert board.standings()[0]["entities"] == 1


def test_domestic_contacts_can_be_allowed_back_in():
    board = board_for("dx", {"count_domestic": True})
    assert board.add(qso(call="W1ABC", grid="EM19")) is None


def test_every_dx_contact_becomes_a_marker_on_the_globe():
    board = board_for("dx")
    board.add(qso(call="JA1XYZ", grid="PM95"))
    (marker,) = board.snapshot()["markers"]
    assert marker["country"] == "Japan"
    assert marker["team"] == "KSU"
    assert abs(marker["lat"] - 35.5) < 1 and abs(marker["lon"] - 139.0) < 1


def test_a_contact_with_no_grid_scores_but_cannot_be_plotted():
    """A missing grid is a marker we can't place, not a contact we refuse."""
    board = board_for("dx")
    assert board.add(qso(call="DL1ABC", grid="")) is None
    assert board.snapshot()["markers"] == []


def test_the_marker_list_is_capped():
    """A scoreboard on a phone should not be sent a megabyte of JSON."""
    board = board_for("dx")
    for i in range(board.mode.MARKER_LIMIT + 50):
        board.add(qso(call=f"DL{i % 10}A{i}", grid="JO41"))
    assert len(board.snapshot()["markers"]) == board.mode.MARKER_LIMIT


# ===================== mode selection =====================

def test_an_unknown_mode_fails_loudly():
    with pytest.raises(SystemExit) as err:
        build("battleship")
    assert "battleship" in str(err.value)


def test_the_snapshot_says_which_view_to_draw():
    assert board_for("classic").snapshot()["contest"]["view"] == "standings"
    assert board_for("conquest").snapshot()["contest"]["view"] == "usmap"
    assert board_for("dx").snapshot()["contest"]["view"] == "globe"
