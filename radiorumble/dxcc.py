"""Callsign prefix to country, for DX mode.

"DX" means a contact outside your own country. Deciding that from a callsign
is prefix matching: the leading letters and first digit identify the licensing
authority, so W5, K4 and AA1 are all the United States while G0, DL1 and JA3
are not.

This is a working subset, not the full DXCC list — around 130 entities chosen
to cover what a station in Kansas running 100 watts of FT8 actually hears in
an afternoon, plus the US territories that are separate DXCC entities despite
carrying US-style callsigns. Anything unmatched is reported as DX with an
unknown country rather than being dropped, because the alternative is
silently refusing to score a legitimate contact.

Portable indicators are handled the way contest software does it: in
``W1ABC/VE3`` the *other* part wins, because that is where the operator is.
"""
from __future__ import annotations

import re

# US mainland prefixes. These are the callsigns that are *not* DX for a US
# contest, and they are also what the conquest map treats as domestic.
US_PREFIXES = (
    "K", "N", "W",
    "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK", "AL",
)

# US territories: US-style callsigns, separate DXCC entities, so they count
# as DX. Checked before the mainland prefixes because KH6 starts with K.
US_TERRITORIES = {
    "KH0": ("Mariana Islands", "OC"), "KH1": ("Baker & Howland", "OC"),
    "KH2": ("Guam", "OC"),            "KH3": ("Johnston Island", "OC"),
    "KH4": ("Midway Island", "OC"),   "KH5": ("Palmyra & Jarvis", "OC"),
    "KH6": ("Hawaii", "OC"),          "KH7": ("Hawaii", "OC"),
    "KH8": ("American Samoa", "OC"),  "KH9": ("Wake Island", "OC"),
    "KL": ("Alaska", "NA"),           "AL": ("Alaska", "NA"),
    "NL": ("Alaska", "NA"),           "WL": ("Alaska", "NA"),
    "KP1": ("Navassa Island", "NA"),  "KP2": ("US Virgin Islands", "NA"),
    "KP3": ("Puerto Rico", "NA"),     "KP4": ("Puerto Rico", "NA"),
    "KP5": ("Desecheo Island", "NA"),
    "NP2": ("US Virgin Islands", "NA"), "NP3": ("Puerto Rico", "NA"),
    "NP4": ("Puerto Rico", "NA"), "WP2": ("US Virgin Islands", "NA"),
    "WP3": ("Puerto Rico", "NA"), "WP4": ("Puerto Rico", "NA"),
}

# (prefix, country, continent). Longest match wins, so specific entries such
# as "VP8" are found before the "V" family they sit inside.
ENTITIES: tuple[tuple[str, str, str], ...] = (
    # North America
    ("VE", "Canada", "NA"), ("VA", "Canada", "NA"), ("VO", "Canada", "NA"),
    ("VY", "Canada", "NA"), ("CY", "Canada", "NA"),
    ("XE", "Mexico", "NA"), ("XF", "Mexico", "NA"), ("4A", "Mexico", "NA"),
    ("6D", "Mexico", "NA"), ("6E", "Mexico", "NA"),
    ("CO", "Cuba", "NA"), ("CM", "Cuba", "NA"),
    ("HI", "Dominican Republic", "NA"), ("HH", "Haiti", "NA"),
    ("6Y", "Jamaica", "NA"), ("8P", "Barbados", "NA"), ("9Y", "Trinidad", "NA"),
    ("ZF", "Cayman Islands", "NA"), ("C6", "Bahamas", "NA"),
    ("V2", "Antigua", "NA"), ("J3", "Grenada", "NA"), ("J6", "St Lucia", "NA"),
    ("J7", "Dominica", "NA"), ("J8", "St Vincent", "NA"),
    ("V4", "St Kitts & Nevis", "NA"), ("PJ", "Curacao", "NA"),
    ("FM", "Martinique", "NA"), ("FG", "Guadeloupe", "NA"),
    ("TG", "Guatemala", "NA"), ("YS", "El Salvador", "NA"),
    ("HR", "Honduras", "NA"), ("YN", "Nicaragua", "NA"),
    ("TI", "Costa Rica", "NA"), ("HP", "Panama", "NA"),
    ("V3", "Belize", "NA"), ("OX", "Greenland", "NA"),
    # South America
    ("PY", "Brazil", "SA"), ("PP", "Brazil", "SA"), ("PT", "Brazil", "SA"),
    ("PU", "Brazil", "SA"), ("PR", "Brazil", "SA"), ("ZZ", "Brazil", "SA"),
    ("LU", "Argentina", "SA"), ("CE", "Chile", "SA"), ("CA", "Chile", "SA"),
    ("CX", "Uruguay", "SA"), ("CP", "Bolivia", "SA"), ("OA", "Peru", "SA"),
    ("HC", "Ecuador", "SA"), ("HK", "Colombia", "SA"), ("YV", "Venezuela", "SA"),
    ("ZP", "Paraguay", "SA"), ("8R", "Guyana", "SA"), ("PZ", "Suriname", "SA"),
    ("FY", "French Guiana", "SA"), ("VP8", "Falkland Islands", "SA"),
    # Europe
    ("G", "England", "EU"), ("M", "England", "EU"), ("2E", "England", "EU"),
    ("GM", "Scotland", "EU"), ("MM", "Scotland", "EU"),
    ("GW", "Wales", "EU"), ("MW", "Wales", "EU"),
    ("GI", "Northern Ireland", "EU"), ("MI", "Northern Ireland", "EU"),
    ("GD", "Isle of Man", "EU"), ("GJ", "Jersey", "EU"), ("GU", "Guernsey", "EU"),
    ("EI", "Ireland", "EU"), ("EJ", "Ireland", "EU"),
    ("DL", "Germany", "EU"), ("DA", "Germany", "EU"), ("DB", "Germany", "EU"),
    ("DC", "Germany", "EU"), ("DD", "Germany", "EU"), ("DF", "Germany", "EU"),
    ("DG", "Germany", "EU"), ("DH", "Germany", "EU"), ("DJ", "Germany", "EU"),
    ("DK", "Germany", "EU"), ("DM", "Germany", "EU"), ("DO", "Germany", "EU"),
    ("F", "France", "EU"), ("TM", "France", "EU"),
    ("I", "Italy", "EU"), ("IK", "Italy", "EU"), ("IZ", "Italy", "EU"),
    ("EA", "Spain", "EU"), ("EB", "Spain", "EU"), ("EC", "Spain", "EU"),
    ("ED", "Spain", "EU"), ("EE", "Spain", "EU"), ("EF", "Spain", "EU"),
    ("EA6", "Balearic Islands", "EU"), ("EA8", "Canary Islands", "AF"),
    ("EA9", "Ceuta & Melilla", "AF"),
    ("CT", "Portugal", "EU"), ("CU", "Azores", "EU"), ("CT3", "Madeira", "AF"),
    ("PA", "Netherlands", "EU"), ("PB", "Netherlands", "EU"),
    ("PC", "Netherlands", "EU"), ("PD", "Netherlands", "EU"),
    ("PE", "Netherlands", "EU"), ("PF", "Netherlands", "EU"),
    ("PG", "Netherlands", "EU"), ("PH", "Netherlands", "EU"),
    ("PI", "Netherlands", "EU"),
    ("ON", "Belgium", "EU"), ("OO", "Belgium", "EU"), ("OT", "Belgium", "EU"),
    ("LX", "Luxembourg", "EU"), ("HB", "Switzerland", "EU"),
    ("HB0", "Liechtenstein", "EU"), ("OE", "Austria", "EU"),
    ("OK", "Czech Republic", "EU"), ("OL", "Czech Republic", "EU"),
    ("OM", "Slovakia", "EU"), ("HA", "Hungary", "EU"), ("HG", "Hungary", "EU"),
    ("SP", "Poland", "EU"), ("SN", "Poland", "EU"), ("SQ", "Poland", "EU"),
    ("SM", "Sweden", "EU"), ("SA", "Sweden", "EU"), ("SB", "Sweden", "EU"),
    ("LA", "Norway", "EU"), ("LB", "Norway", "EU"), ("LN", "Norway", "EU"),
    ("OZ", "Denmark", "EU"), ("OY", "Faroe Islands", "EU"),
    ("OH", "Finland", "EU"), ("OF", "Finland", "EU"), ("OH0", "Aland Islands", "EU"),
    ("TF", "Iceland", "EU"), ("ES", "Estonia", "EU"), ("YL", "Latvia", "EU"),
    ("LY", "Lithuania", "EU"), ("EW", "Belarus", "EU"), ("UR", "Ukraine", "EU"),
    ("UT", "Ukraine", "EU"), ("UU", "Ukraine", "EU"), ("UX", "Ukraine", "EU"),
    ("UY", "Ukraine", "EU"), ("UZ", "Ukraine", "EU"),
    ("ER", "Moldova", "EU"), ("YO", "Romania", "EU"), ("LZ", "Bulgaria", "EU"),
    ("SV", "Greece", "EU"), ("SW", "Greece", "EU"), ("SX", "Greece", "EU"),
    ("SY", "Greece", "EU"), ("SZ", "Greece", "EU"),
    ("9A", "Croatia", "EU"), ("S5", "Slovenia", "EU"), ("E7", "Bosnia", "EU"),
    ("YU", "Serbia", "EU"), ("YT", "Serbia", "EU"), ("4O", "Montenegro", "EU"),
    ("Z3", "North Macedonia", "EU"), ("ZA", "Albania", "EU"),
    ("9H", "Malta", "EU"), ("5B", "Cyprus", "AS"), ("T7", "San Marino", "EU"),
    ("HV", "Vatican", "EU"), ("3A", "Monaco", "EU"), ("C3", "Andorra", "EU"),
    ("UA", "Russia", "EU"), ("UB", "Russia", "EU"), ("UC", "Russia", "EU"),
    ("UD", "Russia", "EU"), ("UE", "Russia", "EU"), ("UF", "Russia", "EU"),
    ("UG", "Russia", "EU"), ("UH", "Russia", "EU"), ("UI", "Russia", "EU"),
    ("RA", "Russia", "EU"), ("RK", "Russia", "EU"), ("RN", "Russia", "EU"),
    ("RU", "Russia", "EU"), ("RV", "Russia", "EU"), ("RW", "Russia", "EU"),
    ("RX", "Russia", "EU"), ("RZ", "Russia", "EU"), ("R", "Russia", "EU"),
    # Asia
    ("JA", "Japan", "AS"), ("JE", "Japan", "AS"), ("JF", "Japan", "AS"),
    ("JG", "Japan", "AS"), ("JH", "Japan", "AS"), ("JI", "Japan", "AS"),
    ("JJ", "Japan", "AS"), ("JK", "Japan", "AS"), ("JL", "Japan", "AS"),
    ("JM", "Japan", "AS"), ("JN", "Japan", "AS"), ("JO", "Japan", "AS"),
    ("JP", "Japan", "AS"), ("JQ", "Japan", "AS"), ("JR", "Japan", "AS"),
    ("JS", "Japan", "AS"), ("7J", "Japan", "AS"), ("7K", "Japan", "AS"),
    ("7L", "Japan", "AS"), ("7M", "Japan", "AS"), ("7N", "Japan", "AS"),
    ("8J", "Japan", "AS"),
    ("HL", "South Korea", "AS"), ("DS", "South Korea", "AS"),
    ("6K", "South Korea", "AS"), ("6L", "South Korea", "AS"),
    ("BY", "China", "AS"), ("BA", "China", "AS"), ("BD", "China", "AS"),
    ("BG", "China", "AS"), ("BH", "China", "AS"), ("BI", "China", "AS"),
    ("BV", "Taiwan", "AS"), ("VR", "Hong Kong", "AS"), ("XX9", "Macao", "AS"),
    ("VU", "India", "AS"), ("AP", "Pakistan", "AS"), ("S2", "Bangladesh", "AS"),
    ("4S", "Sri Lanka", "AS"), ("8Q", "Maldives", "AS"), ("9N", "Nepal", "AS"),
    ("HS", "Thailand", "AS"), ("E2", "Thailand", "AS"),
    ("XV", "Vietnam", "AS"), ("XU", "Cambodia", "AS"), ("XW", "Laos", "AS"),
    ("9V", "Singapore", "AS"), ("9M", "Malaysia", "AS"),
    ("YB", "Indonesia", "OC"), ("YC", "Indonesia", "OC"), ("YD", "Indonesia", "OC"),
    ("DU", "Philippines", "OC"), ("DV", "Philippines", "OC"),
    ("DW", "Philippines", "OC"), ("DX", "Philippines", "OC"),
    ("UN", "Kazakhstan", "AS"), ("EX", "Kyrgyzstan", "AS"),
    ("EY", "Tajikistan", "AS"), ("EZ", "Turkmenistan", "AS"),
    ("UK", "Uzbekistan", "AS"), ("4L", "Georgia", "AS"), ("EK", "Armenia", "AS"),
    ("4J", "Azerbaijan", "AS"), ("4K", "Azerbaijan", "AS"),
    ("TA", "Turkey", "AS"), ("TB", "Turkey", "AS"), ("TC", "Turkey", "AS"),
    ("4X", "Israel", "AS"), ("4Z", "Israel", "AS"), ("JY", "Jordan", "AS"),
    ("OD", "Lebanon", "AS"), ("YK", "Syria", "AS"), ("YI", "Iraq", "AS"),
    ("EP", "Iran", "AS"), ("A4", "Oman", "AS"), ("A6", "United Arab Emirates", "AS"),
    ("A7", "Qatar", "AS"), ("A9", "Bahrain", "AS"), ("9K", "Kuwait", "AS"),
    ("HZ", "Saudi Arabia", "AS"), ("7Z", "Saudi Arabia", "AS"),
    ("BS7", "Scarborough Reef", "AS"),
    # Africa
    ("ZS", "South Africa", "AF"), ("ZR", "South Africa", "AF"),
    ("ZT", "South Africa", "AF"), ("ZU", "South Africa", "AF"),
    ("CN", "Morocco", "AF"), ("7X", "Algeria", "AF"), ("3V", "Tunisia", "AF"),
    ("5A", "Libya", "AF"), ("SU", "Egypt", "AF"), ("ST", "Sudan", "AF"),
    ("ET", "Ethiopia", "AF"), ("5Z", "Kenya", "AF"), ("5H", "Tanzania", "AF"),
    ("5X", "Uganda", "AF"), ("9J", "Zambia", "AF"), ("Z2", "Zimbabwe", "AF"),
    ("C9", "Mozambique", "AF"), ("V5", "Namibia", "AF"), ("A2", "Botswana", "AF"),
    ("7P", "Lesotho", "AF"), ("3DA", "Eswatini", "AF"),
    ("5R", "Madagascar", "AF"), ("3B8", "Mauritius", "AF"),
    ("3B9", "Rodrigues Island", "AF"), ("S7", "Seychelles", "AF"),
    ("FR", "Reunion", "AF"), ("D4", "Cape Verde", "AF"),
    ("EL", "Liberia", "AF"), ("9G", "Ghana", "AF"), ("5N", "Nigeria", "AF"),
    ("TU", "Ivory Coast", "AF"), ("6W", "Senegal", "AF"), ("C5", "Gambia", "AF"),
    ("TR", "Gabon", "AF"), ("TJ", "Cameroon", "AF"), ("9Q", "DR Congo", "AF"),
    ("D2", "Angola", "AF"), ("ZD7", "St Helena", "AF"),
    ("ZD8", "Ascension Island", "AF"), ("ZD9", "Tristan da Cunha", "AF"),
    # Oceania
    ("VK", "Australia", "OC"), ("AX", "Australia", "OC"),
    ("VK9", "Australia (offshore)", "OC"), ("VK0", "Heard/Macquarie", "OC"),
    ("ZL", "New Zealand", "OC"), ("ZM", "New Zealand", "OC"),
    ("P2", "Papua New Guinea", "OC"), ("YJ", "Vanuatu", "OC"),
    ("3D2", "Fiji", "OC"), ("5W", "Samoa", "OC"), ("A3", "Tonga", "OC"),
    ("E5", "Cook Islands", "OC"), ("FO", "French Polynesia", "OC"),
    ("FK", "New Caledonia", "OC"), ("T2", "Tuvalu", "OC"),
    ("T30", "Kiribati", "OC"), ("V6", "Micronesia", "OC"),
    ("V7", "Marshall Islands", "OC"), ("T8", "Palau", "OC"),
    ("KH0", "Mariana Islands", "OC"),
    # Antarctica and the far south
    ("VP8", "Falkland Islands", "SA"), ("CE9", "Antarctica", "AN"),
    ("KC4", "Antarctica", "AN"), ("RI1", "Antarctica", "AN"),
)

# Longest prefix first, so VP8 beats V and EA8 beats EA.
_SORTED = tuple(sorted(ENTITIES, key=lambda e: -len(e[0])))
_TERRITORIES = tuple(sorted(US_TERRITORIES.items(), key=lambda e: -len(e[0])))
_US = tuple(sorted(US_PREFIXES, key=len, reverse=True))

_CALL = re.compile(r"^[A-Z0-9]{1,3}[0-9][A-Z0-9]*$")

UNKNOWN = "Unknown"


def base_call(callsign: str) -> str:
    """Strip portable indicators, keeping the part that says where they are.

    ``W1ABC/VE3`` is a US operator in Canada, and the contact is with Canada.
    ``/P``, ``/M``, ``/QRP`` and a bare digit say nothing about location, so
    they are discarded and the home call kept.
    """
    call = callsign.upper().strip()
    if "/" not in call:
        return call

    parts = [p for p in call.split("/") if p]
    if not parts:
        return call

    ignorable = {"P", "M", "MM", "AM", "QRP", "A", "R", "LH", "B"}
    candidates = [p for p in parts if p not in ignorable and not p.isdigit()]
    if not candidates:
        return parts[0]
    if len(candidates) == 1:
        return candidates[0]

    # Two real parts: the shorter one is the location prefix, as in W1ABC/VE3.
    # Equal length falls back to the first, which is the home call.
    a, b = candidates[0], candidates[1]
    return b if len(b) < len(a) else a


def lookup(callsign: str) -> tuple[str, str, bool]:
    """Return (country, continent, is_dx) for a callsign.

    ``is_dx`` is from a United States point of view: anything that is not a
    mainland US callsign counts, including US territories, which are separate
    DXCC entities even though KP4 and KH6 look domestic.
    """
    call = base_call(callsign)
    if not call:
        return (UNKNOWN, "", True)

    for prefix, (country, continent) in _TERRITORIES:
        if call.startswith(prefix):
            return (country, continent, True)

    for prefix, country, continent in _SORTED:
        if call.startswith(prefix):
            return (country, continent, True)

    for prefix in _US:
        if call.startswith(prefix):
            return ("United States", "NA", False)

    return (UNKNOWN, "", True)


def is_dx(callsign: str) -> bool:
    return lookup(callsign)[2]


def country(callsign: str) -> str:
    return lookup(callsign)[0]
