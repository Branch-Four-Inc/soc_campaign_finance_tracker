<<<<<<< HEAD
# soc_campaign_finance_tracker
Campaign finance tracker for local and state-level candidates representing Hudson County, NJ

=======
# leveler_campaign_finance_tracker
Campaign finance tracker for local and state-level candidates representing Hudson County, NJ

Weblink: https://branch-four-inc.github.io/leveler_campaign_finance_tracker/

## How to run

1. Run `python scrape_data.py` to grab all candidates and their data from the [NJ campaign finance website](https://www.njelecefilesearch.com/SearchCandidateReports). Adjust the configuration in that file as necessary.

2. Provide the following paramters:
    1. `input_dir`: folder containing raw contributions csv files
    2. `output_dir`: output folder 
    3. `contribution_start`: start date of contributions in yyyy-mm-dd format. Start date should be the first day after the last election. Example: if the election was on November 5, 2024, the contribution start date would be November 6, 2024. 
    4. `contribution_end`: end date of contributions in yyyy-mm-dd format
    5. newsroom: name of the newsroom

>>>>>>> 6a2617f4c6969032b8ed5bb5999c842cee95fbbb
