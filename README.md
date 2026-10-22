# soc_campaign_finance_tracker
Campaign finance tracker for local candidates representing towns in Hudson County, NJ

Weblink: https://branch-four-inc.github.io/leveler_campaign_finance_tracker/

## How to run

Run everything from the repository root. The scripts need Python with `pandas`, `numpy`, `python-dateutil`, `requests` and `selenium`, plus Chrome for the scraping step.

### Run the whole pipeline

```
python data_script/run_all.py COUNTY YEAR NEWSROOM STATE DATA_SOURCE
```

Example:

```
python data_script/run_all.py "HUDSON COUNTY" 2026 "Slice of Culture" NJ "NJ Election Law Enforcement Commission"
```

| Argument | Description |
|---|---|
| `COUNTY` | County name exactly as shown on the [NJ ELEC search site](https://www.njelecefilesearch.com/SearchCandidateReports), e.g. `"HUDSON COUNTY"` |
| `YEAR` | Election year, e.g. `2026` (or `ALL` for the scraper) |
| `NEWSROOM` | Name of the newsroom shown in the UI |
| `STATE` | Two-letter state code, e.g. `NJ` |
| `DATA_SOURCE` | Source of the data shown in the UI |

The steps run in order and the pipeline stops at the first one that fails.

### Run the steps individually

1. **Scrape** the candidates and their contributions from the NJ campaign finance website:

   ```
   python data_script/01_scrape_data.py COUNTY YEAR
   ```

   Files are saved to `raw_contributions/<COUNTY>/<YYYY-MM-DD>/`, with a new dated folder for each day the data is pulled. Other settings (office filter, headless mode) are constants at the top of the script.

2. **Summarize** the contributions for the UI:

   ```
   python data_script/02_summarize_contributions.py COUNTY YEAR NEWSROOM STATE DATA_SOURCE
   ```

   Reads the most recent dated folder in `raw_contributions/<COUNTY>/` and writes CSVs to `data_output/<COUNTY>/`. The data window is the five years ending today.

3. **Create summary-page stats** (top fundraisers, largest fundraising gaps, etc.):

   ```
   python data_script/03_create_summary_stats.py COUNTY
   ```

   Reads `data_output/<COUNTY>/` and writes CSVs to `data_output/<COUNTY>/summary_page/`.

### Notes

- Candidate-name cleanup in step 2 is defined only for `HUDSON COUNTY` and `ESSEX COUNTY`. Other counties need an entry added to `CNTY_MAP` in `02_summarize_contributions.py`.
- Each script's docstring has the full usage details.
