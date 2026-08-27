import pandas as pd
import re

states = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
}

state_lookup = {k.lower(): v for k, v in states.items()}


def clean_amount(series):
    return (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA})
        .astype(float)
    )


def clean_donor_name(name_series:pd.Series):
    # Standardize names
    return (
        name_series.astype(str).str.strip()
        .str.lower()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", "", regex=True)
        # replace Dr. in the name
        .str.replace(r"^\s*dr\.?\b", "", flags=re.IGNORECASE, regex=True)
        .str.title()
    )



def round_amount(amount):

    return round(amount, 0)


def standardize_address(address: str) -> str:
    """
    Standardize a US-style street address: abbreviates directional words,
    street suffixes (Street -> St, Avenue -> Ave, etc.), and apartment/unit
    designators (Apartment -> Apt, Suite -> Ste, Number/# -> #, etc.),
    following USPS-style conventions.

    Notes / limitations:
      - Assumes the first token is the house number.
      - Assumes standard US ordering: <number> <street name> <suffix>,
        [<unit designator> <unit number>]. Non-standard orderings (e.g. a
        unit designator appearing before the street name) aren't supported.
      - Only the LAST street-suffix-like word before any unit designator,
        digit, or comma is treated as the actual suffix. This avoids
        mis-abbreviating street names that happen to contain suffix words,
        e.g. "Court Street" -> "Court St" (not "Ct St"),
             "Lake Shore Drive" -> "Lake Shore Dr" (not "Lake Shr Dr").
      - Directional words (North, NW, etc.) are abbreviated wherever they
        appear in the street-name portion.
      - This is a lightweight heuristic parser, not a full USPS CASS-certified
        normalizer -- edge cases (PO boxes, rural routes, non-US formats)
        aren't handled.

    Examples:
        >>> standardize_address("123 North Main Street, Apartment 4b")
        '123 N Main St Apt 4B'
        >>> standardize_address("456 Elm Avenue, SUITE 100")
        '456 Elm Ave Ste 100'
        >>> standardize_address("300 Court Street Building A Floor 2")
        '300 Court St Bldg A Fl 2'
    """
    if not address or not address.strip():
        return address

    STREET_SUFFIXES = {
        "street": "St",
        "avenue": "Ave",
        "boulevard": "Blvd",
        "drive": "Dr",
        "court": "Ct",
        "lane": "Ln",
        "road": "Rd",
        "place": "Pl",
        "square": "Sq",
        "terrace": "Ter",
        "trail": "Trl",
        "parkway": "Pkwy",
        "highway": "Hwy",
        "circle": "Cir",
        "alley": "Aly",
        "crossing": "Xing",
        "expressway": "Expy",
        "freeway": "Fwy",
        "junction": "Jct",
        "pike": "Pike",
        "plaza": "Plz",
        "point": "Pt",
        "ridge": "Rdg",
        "route": "Rte",
        "station": "Sta",
        "turnpike": "Tpke",
        "crescent": "Cres",
        "cove": "Cv",
        "creek": "Crk",
        "extension": "Ext",
        "bend": "Bnd",
        "bridge": "Brg",
        "brook": "Brk",
        "canyon": "Cyn",
        "causeway": "Cswy",
        "cliff": "Clf",
        "club": "Clb",
        "common": "Cmn",
        "corner": "Cor",
        "cottage": "Cotg",
        "garden": "Gdn",
        "gateway": "Gtwy",
        "glen": "Gln",
        "green": "Grn",
        "grove": "Grv",
        "harbor": "Hbr",
        "heights": "Hts",
        "hill": "Hl",
        "hollow": "Holw",
        "island": "Is",
        "knoll": "Knl",
        "landing": "Lndg",
        "meadow": "Mdw",
        "mill": "Ml",
        "mount": "Mt",
        "mountain": "Mtn",
        "orchard": "Orch",
        "park": "Park",
        "pass": "Pass",
        "path": "Path",
        "pine": "Pne",
        "port": "Prt",
        "prairie": "Pr",
        "rapid": "Rpd",
        "rest": "Rst",
        "shore": "Shr",
        "spring": "Spg",
        "summit": "Smt",
        "track": "Trak",
        "trace": "Trce",
        "tunnel": "Tunl",
        "union": "Un",
        "valley": "Vly",
        "view": "Vw",
        "village": "Vlg",
        "ville": "Vl",
        "vista": "Vis",
        "walk": "Walk",
        "way": "Way",
        "wells": "Wls",
    }

    DIRECTIONS = {
        "north": "N",
        "south": "S",
        "east": "E",
        "west": "W",
        "northeast": "NE",
        "northwest": "NW",
        "southeast": "SE",
        "southwest": "SW",
    }

    UNIT_DESIGNATORS = {
        "apartment": "Apt",
        "apt": "Apt",
        "building": "Bldg",
        "bldg": "Bldg",
        "basement": "Bsmt",
        "department": "Dept",
        "floor": "Fl",
        "fl": "Fl",
        "front": "Frnt",
        "hangar": "Hngr",
        "lobby": "Lbby",
        "lot": "Lot",
        "lower": "Lowr",
        "office": "Ofc",
        "penthouse": "Ph",
        "pier": "Pier",
        "rear": "Rear",
        "room": "Rm",
        "rm": "Rm",
        "side": "Side",
        "slip": "Slip",
        "space": "Spc",
        "stop": "Stop",
        "suite": "Ste",
        "ste": "Ste",
        "trailer": "Trlr",
        "unit": "Unit",
        "upper": "Uppr",
        "number": "#",
        "num": "#",
        "no": "#",
    }

    addr = re.sub(r"\s+", " ", address.strip())
    addr = addr.replace(".", "")
    addr = re.sub(r"#\s*", "# ", addr)

    raw_tokens = addr.split(" ")
    n = len(raw_tokens)
    if n == 0:
        return addr

    def split_punct(tok):
        m = re.match(r"^(.*?)([,;:]*)$", tok)
        return m.group(1), m.group(2)

    # Find where the "street name + suffix" run ends: at the first unit
    # designator, a second digit-only token, or a token with trailing comma.
    boundary = n
    for i in range(1, n):
        core, punct = split_punct(raw_tokens[i])
        if core == "":
            continue
        if core.isdigit():
            boundary = i
            break
        if core.lower() in UNIT_DESIGNATORS:
            boundary = i
            break
        if punct:
            boundary = i + 1
            break

    # Within that run, only the RIGHTMOST street-suffix match gets abbreviated.
    suffix_idx = -1
    for i in range(1, boundary):
        core, _ = split_punct(raw_tokens[i])
        if core.lower() in STREET_SUFFIXES:
            suffix_idx = i

    result = []

    # Token 0: house number (or leading alphanumeric like "123A")
    tok0 = raw_tokens[0]
    if re.search(r"\d", tok0) and re.search(r"[A-Za-z]", tok0):
        result.append(tok0.upper())
    else:
        result.append(tok0)

    for i in range(1, n):
        tok = raw_tokens[i]
        core, punct = split_punct(tok)
        if core == "":
            result.append(tok)
            continue
        key = core.lower()
        in_name_run = 1 <= i < boundary

        if key in DIRECTIONS:
            result.append(DIRECTIONS[key] + punct)
        elif in_name_run and i == suffix_idx:
            result.append(STREET_SUFFIXES[key] + punct)
        elif not in_name_run and key in UNIT_DESIGNATORS:
            result.append(UNIT_DESIGNATORS[key] + punct)
        elif re.search(r"\d", core):
            result.append(
                (core.upper() if re.search(r"[A-Za-z]", core) else core) + punct
            )
        elif core.isalpha():
            result.append(core.capitalize() + punct)
        else:
            result.append(tok)

    standardized = " ".join(result)
    standardized = standardized.replace(",", "")  # drop commas entirely
    standardized = re.sub(r"\s+", " ", standardized).strip()
    standardized = re.sub(r"#\s+(?=\S)", "#", standardized)  # "# 5" -> "#5"
    return standardized