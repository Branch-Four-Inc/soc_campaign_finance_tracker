#!/usr/bin/env python3
"""
NJ ELEC Contribution Data Scraper
==================================

Downloads a candidate list and detailed contribution data for every
candidate in a given county for a given year from the NJ ELEC e-filing
search site (https://www.njelecefilesearch.com), by calling the site's own
backing JSON APIs:

  - Candidate discovery:   POST /api/VWEntity/GetEntitiesByObject
                            (endpoint: /api/VWEntity/Entities20)
  - Contribution detail:   POST /api/VWContributionDetail/GetContBitsDataByObject

Selenium is used to load the search page once to read the Location and Office 
dropdowns' codes which aren't present in the plain page HTML. Once
those codes are collected, everything runs as plain HTTP calls.

CONFIGURATION
-------------
Edit the constants in the CONFIG section below.
"""

import os
import re
import csv
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# ============================== CONFIG ===============================

BASE_URL = "https://www.njelecefilesearch.com"
SEARCH_URL = f"{BASE_URL}/SearchCandidateReports"
SUMMARY_URL_TMPL = f"{BASE_URL}/SummaryData?eid={{eid}}"
ENTITIES_API_URL = f"{BASE_URL}/api/VWEntity/Entities20"
CONTRIB_API_URL = f"{BASE_URL}/api/VWContributionDetail/GetContBitsDataByObject"

COUNTY_TEXT = "ESSEX COUNTY"  # <-- set to the county you want
YEAR_TEXT = "2026"  # <-- election year (or "ALL")
OFFICE_TEXT = "ALL"  # <-- office filter, "ALL" for everything
INCLUDE_COUNTY_WIDE_OPTION = True  # also search the bare county option
NONPAC_ONLY = True  # matches the site default (candidates/committees, not PACs)

OUTPUT_DIR = os.path.abspath(f"./raw_contributions/{COUNTY_TEXT}")

HEADLESS = False  # set True once everything's confirmed working
WAIT_TIMEOUT = 20  # seconds to wait for elements
PAUSE_BETWEEN_CANDIDATES = 0.3  # be polite to the server between API calls
API_PAGE_LENGTH = 100  # rows per DataTables "page" when paging through either API

# Field name for a candidate/entity's ID in the Entities20 response
CANDIDATE_ID_FIELD = "ENTITY_S"

# The DataTables column definitions the site's own front-end sends for the
# candidate/entity grid.
ENTITY_COLUMNS = [
    ("ENTITYNAME", "ENTITYNAME"),
    ("LOCATION", "LOCATION"),
    ("OFFICE", "OFFICE"),
    ("PARTY", "PARTY"),
    ("ELECTIONTYPE", "ELECTIONTYPE"),
    ("ELECTIONYEAR", "ELECTIONYEAR"),
]

# The DataTables column definitions the site's own front-end sends for the
# contribution-detail grid.
CONTRIBUTION_COLUMNS = [
    ("CONTRIBUTOR", "CONTRIBUTOR"),
    ("Address", "STREET1"),
    ("EMP_NAME", "EMP_NAME"),
    ("EmployerAddress", "EMP_STREET1"),
    ("OccupationName", "OccupationName"),
    ("CAND_NAME", "CAND_NAME"),
    ("ContributorType", "ContributorType"),
    ("ContributionType", "ContributionType"),
    ("CONT_DATE", "CONT_DATE"),
    ("CONT_AMT", "CONT_AMT"),
    ("CONTRIB_S", "CONTRIB_S"),
]

# The exact set of fields written to each candidate's contribution-detail TSV. 
OUTPUT_CONTRIBUTION_FIELDS = [
    "IsIndividual",
    "CONTRIBUTOR", # name of contributor -- either individual or business name
    "STREET1",
    "STREET2",
    "CITY",
    "STATE",
    "ZIP",
    # "CONT_TYPE",
    "ContributorType",
    "ContributionType",
    "CONT_DATE",
    "CONT_AMT",
    "ENTITY_S",
]

# =======================================================================


# --------------------------- one-time Selenium step ---------------------


def make_driver():
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def get_dropdown_codes(driver):
    """Load the search page once and read the Location and Office
    dropdowns' own <option value="..."> codes alongside their display
    text. Returns (location_options, office_options), each a list of
    (value, text) tuples in dropdown order."""
    driver.get(SEARCH_URL)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    location_select = wait.until(
        EC.presence_of_element_located((By.ID, "ddlLocationCodes"))
    )
    office_select = driver.find_element(By.ID, "ddlOfficeCodes")

    location_options = [
        (opt.get_attribute("value"), opt.text) for opt in Select(location_select).options
    ]
    office_options = [
        (opt.get_attribute("value"), opt.text) for opt in Select(office_select).options
    ]

    return location_options, office_options


def get_location_codes_for_county(location_options, county_text, include_county_wide=True):
    """Given the (value, text) pairs read from the Location dropdown, find
    the county heading and every subdivision/municipality grouped under
    it (options whose text is prefixed with "----"), and return a list of
    (code, display_name) tuples: county-wide first (if requested),
    followed by each subdivision in dropdown order."""
    county_norm = county_text.strip().upper()

    county_index = None
    for i, (_value, text) in enumerate(location_options):
        if text.strip("- ").upper() == county_norm:
            county_index = i
            break

    if county_index is None:
        raise ValueError(
            f"Could not find '{county_text}' in the Location dropdown. "
            f"Double check the exact spelling/casing used on the site "
            f"(e.g. 'MORRIS COUNTY')."
        )

    subdivisions = []
    for value, text in location_options[county_index + 1 :]:
        if text.startswith("----"):
            subdivisions.append((value, text.strip("- ")))
        else:
            break  # hit the next county heading (or end of this group)

    codes = []
    if include_county_wide:
        codes.append((location_options[county_index][0], location_options[county_index][1].strip("- ")))
    codes.extend(subdivisions)

    return codes


def get_office_code(office_options, office_text):
    """Look up the numeric code for a given office display text.
    Returns "" for "ALL" (no filter), matching the site's own default."""
    if office_text.strip().upper() == "ALL":
        return ""
    office_norm = office_text.strip().upper()
    for value, text in office_options:
        if text.strip().upper() == office_norm:
            return value or ""
    for value, text in office_options:
        if office_norm in text.strip().upper():
            return value or ""
    raise ValueError(
        f"Could not find office '{office_text}' in the Office dropdown."
    )


# ------------------------------ requests API -----------------------------


def make_api_session():
    """Create a requests.Session and prime it with the cookies the site's
    load balancer needs (Azure App Service 'ARRAffinity' session-affinity
    cookies), by hitting a normal page once."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
    )
    session.get(SEARCH_URL, timeout=30)
    return session


def _datatables_base_payload(columns, order, start, length, draw):
    payload = {"draw": str(draw)}
    for i, (data_field, name_field) in enumerate(columns):
        prefix = f"columns[{i}]"
        payload[f"{prefix}[data]"] = data_field
        payload[f"{prefix}[name]"] = name_field
        payload[f"{prefix}[searchable]"] = "true"
        payload[f"{prefix}[orderable]"] = "true"
        payload[f"{prefix}[search][value]"] = ""
        payload[f"{prefix}[search][regex]"] = "false"
    for i, (col, direction, name) in enumerate(order):
        payload[f"order[{i}][column]"] = str(col)
        payload[f"order[{i}][dir]"] = direction
        payload[f"order[{i}][name]"] = name
    payload["start"] = str(start)
    payload["length"] = str(length)
    payload["search[value]"] = ""
    payload["search[regex]"] = "false"
    return payload


def build_entities_payload(location_code, year_text, office_code, start, length, draw):
    payload = _datatables_base_payload(
        ENTITY_COLUMNS,
        [(5, "desc", "ELECTIONYEAR"), (0, "asc", "ENTITYNAME")],
        start,
        length,
        draw,
    )
    payload.update(
        {
            "NONPACOnly": "true" if NONPAC_ONLY else "false",
            "FirstName": "",
            "LastName": "",
            "MI": "",
            "Suffix": "",
            "NonIndName": "",
            "OfficeCodes": office_code or "",
            "PartyCodes": "",
            "LocationCodes": str(location_code) if location_code else "",
            "ElectionTypeCodes": "",
            "ElectionYears": "" if year_text.strip().upper() == "ALL" else str(year_text),
            "SortColumn": "ElectionYear",
            "SortBy": "desc",
        }
    )
    return payload


def build_contribution_payload(entity_s, start, length, draw):
    payload = _datatables_base_payload(
        CONTRIBUTION_COLUMNS,
        [(0, "asc", "CONTRIBUTOR")],
        start,
        length,
        draw,
    )
    payload["ENTITY_S"] = str(entity_s)
    return payload


def extract_entity_id(row):
    """Find the candidate/entity ID in an Entities20 response row."""
    value = row.get(CANDIDATE_ID_FIELD)
    if value not in (None, ""):
        return str(value)
    print(
        f"  [!] Row is missing '{CANDIDATE_ID_FIELD}'. "
        f"Actual keys on this row: {sorted(row.keys())}"
    )
    return None


def fetch_candidates_for_location(session, location_code, location_name, year_text, office_code):
    """Page through the Entities20 API for a given location code and
    return a list of candidate dicts."""
    candidates = []
    start = 0
    draw = 1

    while True:
        payload = build_entities_payload(
            location_code, year_text, office_code, start, API_PAGE_LENGTH, draw
        )
        resp = session.post(ENTITIES_API_URL, data=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("data", []) or []

        for row in rows:
            eid = extract_entity_id(row)
            if not eid:
                continue
            candidates.append(
                {
                    "eid": eid,
                    "name": row.get("ENTITYNAME", ""),
                    "location": row.get("LOCATION", ""),
                    "office_cmte": row.get("OFFICE", ""),
                    "party": row.get("PARTY", ""),
                    "election_type": row.get("ELECTIONTYPE", ""),
                    "year": row.get("ELECTIONYEAR", ""),
                    "search_location": location_name,
                    "raw_row": row,
                }
            )

        total = body.get("recordsFiltered", len(rows))
        start += API_PAGE_LENGTH
        draw += 1
        if not rows or start >= total:
            break
        time.sleep(0.2)

    return candidates


def fetch_all_contribution_rows(session, eid):
    """Page through the contribution-detail API for a given candidate EID
    and return the full list of row dicts."""
    all_rows = []
    start = 0
    draw = 1

    while True:
        payload = build_contribution_payload(eid, start, API_PAGE_LENGTH, draw)
        resp = session.post(CONTRIB_API_URL, data=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("data", []) or []
        all_rows.extend(rows)

        total = body.get("recordsFiltered", len(rows))
        start += API_PAGE_LENGTH
        draw += 1
        if not rows or start >= total:
            break
        time.sleep(0.2)

    return all_rows


# ------------------------------ output writers ----------------------------


def write_contribution_tsv(rows, name, eid):
    """Write only the selected fields from the raw JSON rows for a
    candidate out to a tab-separated file, in a fixed column order."""
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    dest = os.path.join(OUTPUT_DIR, f"{safe_name}_{eid}_contribution_detail.tsv")


    if not rows:
        # with open(dest, "w", newline="", encoding="utf-8") as f:
        #     writer = csv.DictWriter(f, fieldnames=OUTPUT_CONTRIBUTION_FIELDS, delimiter="\t")
        #     writer.writeheader()
        print(f"  [skip] No contributions on file for EID {eid} ({name})")
        return "skipped"

    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_CONTRIBUTION_FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: ("" if row.get(k) is None else row.get(k, "")) for k in OUTPUT_CONTRIBUTION_FIELDS}
            )

    print(f"  [OK] Saved {len(rows)} row(s): {dest}")
    return "downloaded"


def fetch_and_save_contribution_detail(session, name, eid):
    try:
        rows = fetch_all_contribution_rows(session, eid)
    except requests.RequestException as e:
        print(f"  [!] API request failed for EID {eid} ({name}): {e}")
        return "failed"
    try:
        return write_contribution_tsv(rows, name, eid)
    except OSError as e:
        print(f"  [!] Could not write TSV for EID {eid} ({name}): {e}")
        return "failed"


def write_candidates_tsv(all_candidates):
    safe_county = re.sub(r"[^A-Za-z0-9]+", "_", COUNTY_TEXT).strip("_")
    tsv_path = os.path.join(OUTPUT_DIR, f"candidates_{safe_county}_{YEAR_TEXT}.tsv")

    fieldnames = [
        "eid",
        "name",
        "location",
        "office_cmte",
        "party",
        "election_type",
        "year",
        "search_location",
    ]

    with open(tsv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for c in all_candidates.values():
            writer.writerow({k: c.get(k, "") for k in fieldnames})

    print(f"\nSaved full candidate table ({len(all_candidates)} rows) to: {tsv_path}")


# ------------------------------------ main ---------------------------------


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Use Selenium only to read dropdown codes
    driver = make_driver()
    try:
        print("Reading Location/Office dropdown codes ...")
        location_options, office_options = get_dropdown_codes(driver)
    finally:
        driver.quit()

    locations = get_location_codes_for_county(
        location_options, COUNTY_TEXT, INCLUDE_COUNTY_WIDE_OPTION
    )
    office_code = get_office_code(office_options, OFFICE_TEXT)

    print(f"Found {len(locations)} location(s) to search under '{COUNTY_TEXT}':")
    for code, name in locations:
        print(f"   - {name} (code {code})")

    # --- Download everything else using requests
    session = make_api_session()

    all_candidates = {}  # eid -> candidate dict
    print(f"\nSearching each location for YEAR='{YEAR_TEXT}', OFFICE='{OFFICE_TEXT}' ...\n")
    for code, name in locations[0:2]:
        print(f"--- {name} ---")
        try:
            candidates = fetch_candidates_for_location(
                session, code, name, YEAR_TEXT, office_code
            )
        except requests.RequestException as e:
            print(f"  [!] Search failed for '{name}': {e}")
            continue

        if not candidates:
            print("  (no candidates found)")
        for c in candidates:
            if c["eid"] not in all_candidates:
                all_candidates[c["eid"]] = c
                print(f"   - {c['name']} (EID {c['eid']})")

    if not all_candidates:
        print("\nNo candidates found across any location.")
        return

    write_candidates_tsv(all_candidates)

    print(
        f"\nFound {len(all_candidates)} unique candidate(s) total across "
        f"'{COUNTY_TEXT}'. Fetching contribution detail for each via the API...\n"
    )

    downloaded = skipped = failed = 0
    for eid, c in all_candidates.items():
        print(f"[{eid}] {c['name']}  ({c['search_location']})")
        result = fetch_and_save_contribution_detail(session, c["name"], eid)
        if result == "downloaded":
            downloaded += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1
        time.sleep(PAUSE_BETWEEN_CANDIDATES)

    print(
        f"\nDownload summary: {downloaded} downloaded, "
        f"{skipped} skipped (no contributions on file), "
        f"{failed} failed."
    )
    print(f"\nDone. Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()