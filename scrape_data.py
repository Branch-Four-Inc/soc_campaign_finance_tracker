#!/usr/bin/env python3
"""
NJ ELEC Contribution Data Scraper
==================================

Downloads detailed contribution reports for every candidate in a given
county for a given year from the NJ ELEC e-filing search site:

    https://www.njelecefilesearch.com/SearchCandidateReports

It works by reading the Location dropdown's own option list to find every
subdivision (municipality) grouped under the county you specify, then runs
the candidate search separately for the county-wide option and each of its
subdivisions -- since candidates are filed against a single
municipality/subdivision, not "under" the county as a parent record. Results
are de-duplicated by EID in case a candidate ever turns up more than once.

For each candidate found, it visits:

    https://www.njelecefilesearch.com/SummaryData?eid=<EID>

opens the "Contribution Detailed" tab, and -- only if that candidate
actually has contributions on file -- clicks that tab's "Download Data"
button, saving whatever file the site generates (CSV or Excel) into an
output folder, named after the candidate. Candidates with nothing on file
are skipped (nothing downloaded for them), and a summary count of
downloaded/skipped/failed is printed at the end.

It also saves the full table of every candidate found (name, EID,
location, office/committee, party, election type, year) to a single CSV
in the output folder, before any downloading starts -- so you have a
complete roster for the county even if a download fails partway through.


CONFIGURATION
-------------
Edit the constants in the CONFIG section below:
  - COUNTY_TEXT: the exact county option text, e.g. "MORRIS COUNTY"
    (the script will automatically discover and loop over every
    subdivision/municipality listed under it in the dropdown)
  - YEAR_TEXT: e.g. "2026"
  - OFFICE_TEXT: e.g. "ALL", "MAYOR", "STATE ASSEMBLY", etc.
  - INCLUDE_COUNTY_WIDE_OPTION: whether to also run the search against the
    plain county option itself (some county-level offices, like County
    Commissioner, are filed under the county rather than a municipality)
  - OUTPUT_DIR: where downloaded files should end up
"""

import os
import re
import csv
import time
import glob
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ============================== CONFIG ===============================

BASE_URL = "https://www.njelecefilesearch.com"
SEARCH_URL = f"{BASE_URL}/SearchCandidateReports"
SUMMARY_URL_TMPL = f"{BASE_URL}/SummaryData?eid={{eid}}"

COUNTY_TEXT = "HUDSON COUNTY"  # <-- set to the county you want
YEAR_TEXT = "2026"  # <-- election year
OFFICE_TEXT = "ALL"  # <-- office filter, "ALL" for everything
INCLUDE_COUNTY_WIDE_OPTION = True  # also search the bare county option

OUTPUT_DIR = os.path.abspath(f"./raw_contributions/{COUNTY_TEXT}")
DOWNLOAD_TMP_DIR = os.path.abspath("./raw_contributions/_chrome_downloads")

HEADLESS = False  # set True once selectors are confirmed working
WAIT_TIMEOUT = 20  # seconds to wait for elements/downloads
PAUSE_BETWEEN_CANDIDATES = 1.5  # be polite to the server
PAUSE_BETWEEN_LOCATIONS = 2.0  # be polite to the server between subsections

# =======================================================================


def make_driver():
    os.makedirs(DOWNLOAD_TMP_DIR, exist_ok=True)
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    prefs = {
        "download.default_directory": DOWNLOAD_TMP_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def select_by_visible_text_safe(driver, select_element, text):
    """Select a dropdown option, tolerating exact vs. partial text match."""
    sel = Select(select_element)
    try:
        sel.select_by_visible_text(text)
        return True
    except NoSuchElementException:
        for opt in sel.options:
            if text.strip().upper() in opt.text.strip().upper():
                sel.select_by_visible_text(opt.text)
                return True
    return False


def get_locations_for_county(driver, county_text, include_county_wide=True):
    """Load the search page and read the Location dropdown's own option
    list to find every subdivision/municipality grouped under the given
    county.

    The hierarchical Location dropdown lists a county name as one option, followed by
    its municipalities as separate options prefixed with "----".

    Returns a list of location option-text strings, county-wide option
    first (if requested) followed by each subdivision in dropdown order.
    """
    driver.get(SEARCH_URL)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    location_select = wait.until(
        EC.presence_of_element_located((By.ID, "ddlLocationCodes"))
    )
    sel = Select(location_select)
    option_texts = [opt.text for opt in sel.options]

    county_norm = county_text.strip().upper()

    # Find the index of the county heading itself (exact match, ignoring
    # any leading dashes just in case).
    county_index = None
    for i, text in enumerate(option_texts):
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
    for text in option_texts[county_index + 1 :]:
        if text.startswith("----"):
            subdivisions.append(text)
        else:
            break  # hit the next county heading (or end of this group)

    locations = []
    if include_county_wide:
        locations.append(option_texts[county_index])
    locations.extend(subdivisions)

    return locations


def run_candidate_search(driver, location_text, year_text, office_text):
    """Load the search page, set filters, submit, and return a list of
    candidate dicts (name, eid, and the rest of the result row's columns)
    found in the results table."""
    driver.get(SEARCH_URL)

    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    location_select = wait.until(
        EC.presence_of_element_located((By.ID, "ddlLocationCodes"))
    )
    year_select = driver.find_element(By.ID, "ddlElectionYears")
    office_select = driver.find_element(By.ID, "ddlOfficeCodes")

    select_by_visible_text_safe(driver, location_select, location_text)
    select_by_visible_text_safe(driver, year_select, year_text)
    select_by_visible_text_safe(driver, office_select, office_text)

    search_button = driver.find_element(
        By.XPATH,
        "/html/body/div/div/div/div/div[2]/div[1]/div[1]/div/div/div[2]/div[12]/div/button[2]",
    )
    search_button.click()

    # Wait for the results table to populate with at least one row.
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
    time.sleep(2)  # allow AJAX grid to finish rendering

    candidates = []
    rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
    for row in rows:
        try:
            link = row.find_element(By.TAG_NAME, "a")
        except NoSuchElementException:
            continue
        name = link.text.strip()
        if not name:
            continue
        href = link.get_attribute("href") or ""
        onclick = link.get_attribute("onclick") or ""
        combined = href + " " + onclick
        m = re.search(r"eid=(\d+)", combined, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d{5,7})", combined)  # fallback: any 5-7 digit number
        if not m:
            continue
        eid = m.group(1)

        cells = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]

        def cell(i):
            return cells[i] if i < len(cells) else ""

        candidates.append(
            {
                "eid": eid,
                "name": name,
                "location": cell(1),
                "office_cmte": cell(2),
                "party": cell(3),
                "election_type": cell(4),
                "year": cell(5),
                "raw_cells": cells,
            }
        )

    # de-duplicate by eid while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c["eid"] not in seen:
            seen.add(c["eid"])
            unique_candidates.append(c)

    return unique_candidates


def has_contributions(driver):
    """Check whether the Contribution Detailed tab shows any contributions.

    Checks:
      1. The "Total Contributions" figure on the page
      2. Whether the contribution detail table actually has any data rows.
    """
    total_amount = None
    for label in ("Total Contributions", "Toal Contributions", "Total Contribution"):
        try:
            el = driver.find_element(By.XPATH, f"//*[contains(text(),'{label}')]")
            amount_match = re.search(r"[\d,]+\.?\d*", el.text.replace(",", ""))
            if amount_match:
                total_amount = float(amount_match.group(0))
            break
        except (NoSuchElementException, ValueError):
            continue

    if total_amount is not None:
        return total_amount > 0

    # Fallback: no total figure found/parsed
    try:
        table = driver.find_element(
            By.XPATH, "//table[.//*[contains(text(),'Contributor')]]"
        )
        data_rows = [
            r
            for r in table.find_elements(By.TAG_NAME, "tr")
            if r.find_elements(By.TAG_NAME, "td")
        ]
        return len(data_rows) > 0
    except NoSuchElementException:
        # Can't determine either way -- default to "has contributions"
        return True


def download_contribution_detail(driver, name, eid):
    """Visit a candidate's SummaryData page, open Contribution Detailed tab,
    and click Download Data and move the resulting file into OUTPUT_DIR.

    Returns "downloaded", "skipped" (no contributions), or "failed".
    """
    url = SUMMARY_URL_TMPL.format(eid=eid)
    driver.get(url)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    try:
        tab = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="CD"]')))
        tab.click()
        time.sleep(1.5)  # allow the grid to load via AJAX for this tab
    except TimeoutException:
        print(
            f"  [!] Could not find 'Contribution Detailed' tab for EID {eid} ({name})"
        )
        return "failed"

    if not has_contributions(driver):
        print(
            f"  [skip] No contributions on file for EID {eid} ({name}) -- nothing to download."
        )
        return "skipped"

    # Record files already present so we can detect the new one.
    before = set(glob.glob(os.path.join(DOWNLOAD_TMP_DIR, "*")))

    try:
        download_buttons = driver.find_elements(By.XPATH, '//*[@id="btnDownloadData"]')
        clicked = False
        for btn in download_buttons:
            if btn.is_displayed():
                btn.click()
                clicked = True
                break
        if not clicked:
            print(f"  [!] No visible 'Download Data' button for EID {eid} ({name})")
            return "failed"
    except NoSuchElementException:
        print(f"  [!] Could not find 'Download Data' button for EID {eid} ({name})")
        return "failed"

    # Wait for a new file to appear in the Chrome download folder.
    new_file = None
    deadline = time.time() + WAIT_TIMEOUT
    while time.time() < deadline:
        after = set(glob.glob(os.path.join(DOWNLOAD_TMP_DIR, "*")))
        newly_added = [f for f in (after - before) if not f.endswith(".crdownload")]
        if newly_added:
            new_file = newly_added[0]
            break
        time.sleep(0.5)

    if not new_file:
        print(f"  [!] No file downloaded for EID {eid} ({name})")
        return "failed"

    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    ext = os.path.splitext(new_file)[1] or ".csv"
    dest = os.path.join(OUTPUT_DIR, f"{safe_name}_{eid}_contribution_detail{ext}")
    shutil.move(new_file, dest)
    print(f"  [OK] Saved: {dest}")
    return "downloaded"


def write_candidates_csv(all_candidates):
    """Save the full candidate table (every candidate found across the
    county and all its subdivisions) to a CSV file."""
    safe_county = re.sub(r"[^A-Za-z0-9]+", "_", COUNTY_TEXT).strip("_")
    csv_path = os.path.join(OUTPUT_DIR, f"candidates_{safe_county}_{YEAR_TEXT}.csv")

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

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in all_candidates.values():
            writer.writerow({k: c.get(k, "") for k in fieldnames})

    print(f"\nSaved full candidate table ({len(all_candidates)} rows) to: {csv_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    driver = make_driver()

    all_candidates = {}  # eid -> candidate dict

    try:
        print(f"Discovering subdivisions for '{COUNTY_TEXT}' ...")
        locations = get_locations_for_county(
            driver, COUNTY_TEXT, INCLUDE_COUNTY_WIDE_OPTION
        )
        print(f"Found {len(locations)} location(s) to search:")
        for loc in locations:
            print(f"   - {loc.strip('- ')}")

        print(
            f"\nSearching each location for YEAR='{YEAR_TEXT}', OFFICE='{OFFICE_TEXT}' ...\n"
        )
        for loc in locations:
            display_loc = loc.strip("- ")
            print(f"--- {display_loc} ---")
            try:
                candidates = run_candidate_search(driver, loc, YEAR_TEXT, OFFICE_TEXT)
            except Exception as e:
                print(f"  [!] Search failed for '{display_loc}': {e}")
                continue

            if not candidates:
                print("  (no candidates found)")
            for c in candidates:
                if c["eid"] not in all_candidates:
                    c["search_location"] = display_loc
                    all_candidates[c["eid"]] = c
                    print(f"   - {c['name']} (EID {c['eid']})")
                # else: already seen this candidate under another location, skip duplicate

            time.sleep(PAUSE_BETWEEN_LOCATIONS)

        if not all_candidates:
            print(
                "\nNo candidates found across any location (see the ADJUST ME "
                "comments in run_candidate_search / get_locations_for_county)."
            )
            return

        # Save the full candidate table to CSV before downloading anything
        write_candidates_csv(all_candidates)

        print(
            f"\nFound {len(all_candidates)} unique candidate(s) total across "
            f"'{COUNTY_TEXT}'. Downloading contribution detail for each...\n"
        )

        downloaded = skipped = failed = 0
        for eid, c in all_candidates.items():
            print(f"[{eid}] {c['name']}  ({c['search_location']})")
            result = download_contribution_detail(driver, c["name"], eid)
            if result == "downloaded":
                downloaded += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1
            time.sleep(PAUSE_BETWEEN_CANDIDATES)

        print(
            f"\nDownload summary: {downloaded} downloaded, "
            f"{skipped} skipped (no contributions on file), {failed} failed."
        )

    finally:
        driver.quit()
        # Clean up the temp chrome download dir if empty
        try:
            if not os.listdir(DOWNLOAD_TMP_DIR):
                os.rmdir(DOWNLOAD_TMP_DIR)
        except OSError:
            pass

    print(f"\nDone. Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
