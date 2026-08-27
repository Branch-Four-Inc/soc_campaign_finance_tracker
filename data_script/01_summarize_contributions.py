import pandas as pd
<<<<<<< HEAD
import os 
import re
import numpy as np 

def clean_amount(series):
    return (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA})
        .astype(float)
    )


#def clean_donor_name(series):
#    return (
#        series.astype(str)
#        .str.strip()
#        .str.lower()
#        .str.replace(r"[^\w\s]", "", regex=True)
#        .str.replace(r"\s+", "", regex=True)
#    )

def clean_donor_name(name_series, contributor_type_series):
    cleaned = name_series.astype(str).str.strip()

    # Only remove middle names for Individuals
    is_individual = contributor_type_series.eq("Individual")

    def remove_middle(name): ###Middle names are removed to avoid duplicates in the data. For example, "John A. Smith" and "John B. Smith" will be treated as the same contributor. Stella Mach check
        parts = name.split()
        if len(parts) >= 3:
            return f"{parts[0]} {parts[-1]}"
        return name

    cleaned.loc[is_individual] = cleaned.loc[is_individual].apply(remove_middle)

    # Standardize names
    cleaned = (
        cleaned
        .str.lower()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", "", regex=True)
    )

    return cleaned

def find_doctors(df): #No doctor names found in data Stella Mach check
    """
    Return all individual contributors whose names start with
    Dr or Dr.
    """
    doctors = df[
        (df["Contributor Type"] == "Individual") &
        (
            df["Contributor Name"]
            #.str.contains(r"^\s*dr\.?\s", flags=re.IGNORECASE, regex=True, na=False)
            #.str.contains(r"^\s*dr[.\s]", flags=re.IGNORECASE, regex=True, na=False) 
            .str.contains(r"^\s*dr\.?\b", flags=re.IGNORECASE, regex=True, na=False)
        )
    ]

    return doctors

##Check for contributors that have the same cleaned name but are not merged because they differ by city and/or candidate Stella Mach check
def find_unmerged_same_name_contributors(donor_summary):
    """
    Shows contributors that still appear as multiple rows in donor_summary
    with the same cleaned name.

    This helps identify contributors that were not merged because they differ
    by city and/or candidate.
    """

    repeated_names = (
        donor_summary.groupby("Contributor Name_clean")
        .filter(lambda g: len(g) > 1)
        .sort_values(["Contributor Name_clean", "Candidate"])
    )

    return repeated_names

def round_amount(amount):
    
    return(round(amount, 0))
=======
from pathlib import Path
from utils import round_amount, clean_amount
>>>>>>> nj-development



def main(file_format="csv",):

    ############# CONFIG ##########################
    county = "HUDSON COUNTY"
    contribution_start = "2020-01-01"
    newsroom = "Slice of Culture"
    pull_date = "2026-07-21"
    contribution_end = pull_date
    state = "NJ"
    ###############################################

    input_dir = Path(f"raw_contributions/{county}")
    output_dir = Path(f"data_output/{county}")
    candidate_info_dir = input_dir / Path(f"candidates_{'_'.join(county.split(' '))}_2026.csv")
    file_names = input_dir.glob(f"*{file_format}")

    df_list = []

<<<<<<< HEAD
    parser.add_argument("input_dir")
    parser.add_argument("output_dir")
    parser.add_argument("contribution_start")
    parser.add_argument("contribution_end")
    parser.add_argument("newsroom")
    parser.add_argument("file_format")
    
    input_dir = '../raw_contributions/'
    output_dir = '../data_output/'
    contribution_start = "2024-11-06"
    contribution_end = "2026-08-08"
    newsroom = 'The Leveler News'
    
    file_names = [f for f in os.listdir(args.input_dir) if os.path.isfile(os.path.join(args.input_dir, f))]
    
    file_format = "csv"
    
    df_list =[]
    
=======
>>>>>>> nj-development
    # read in all files into one list
    for f in file_names:
        # read all files not including candidate info
        if "candidates_" not in str(f):
            try:
                temp_df = pd.read_csv(f, index_col=False)
                # Save EID from name of the file
                temp_df["CandidateID"] = int(str(f).split("_contribution_detail")[0].split("_")[-1])
                df_list += [temp_df]
            except Exception as e:
                # Most of these are issues with commas in names
                # TODO fix the scraping code to remove these
                raise ValueError(e)

    df = pd.concat(df_list, ignore_index=True)
    # Rename the candidate and Amount columns for clarity
    df.rename(columns={"EntityName": "Candidate", "ContributionAmount":"Amount"}, inplace=True)

    # ----------------------------------------------
    # LOAD IN CANDIDATE INFO
    # ----------------------------------------------
<<<<<<< HEAD
    df.loc[:, ["Candidate", 'State', 'Location', 'Office']] = df.loc[:, ["Candidate", 'State', 'Location', 'Office']].apply(lambda x: x.str.strip().str.title())
    
    df['Location'] = df['Location'].str.replace("Th ", "th ")
    
    candidate_info = df.drop_duplicates(['Candidate'])[['Candidate', 'State', 'Location', 'Office', 'Pull_date']].reset_index(drop = True)
    
    # ADD KISHA SKIPPER IN MANUALLY
    #candidate_info = pd.concat([candidate_info, 
    #           pd.DataFrame({'Candidate': 'Kisha Skipper (D)', 
    #                         'State': 'Ny', 
    #                         'Location': '15th District', 
    #                         'Office': 'County Legislator', 
    #                         'Pull_date': '2026-06-07'}, index = [0])], axis = 0)
    
    # sort candidates
    candidate_info = candidate_info.sort_values(['Location', 'Office', 'Candidate'])
    
=======
>>>>>>> nj-development

    cand_info = pd.read_csv(
        candidate_info_dir
    ).rename(
        columns={
            "name": "Candidate",
            "office_cmte": "Office",
            "election_type": "Election",
            "eid":"CandidateID",
            "party": "Party",
        }
    ).drop_duplicates(["Candidate"]).sort_values(["Office", "Candidate"]).reset_index(drop=True)

    # There are multiple rows for the same candidate based on primary vs full election
    df = pd.merge(df, cand_info, on=["CandidateID", "Candidate"], how="left")

    # ----------------------------------------------
    # ADD EXTRA COLUMNS, CLEAN STRINGS
    # ----------------------------------------------

    df["State"] = "New Jersey"
    # hard-coded for now, as all data was pulled the same day
    df["PullDate"] = pull_date


    # Clean up the values for candidates, individuals, location, etc.
    title_cols = [
        "Candidate",
        "Location",
        "Office",
        "FirstName",
        "LastName",
        "NonIndName",
        "Party",
        "Election",
        "ContributorType",
    ]
    df.loc[:, title_cols] = df.loc[:, title_cols].apply(lambda x: x.str.strip().str.title())

    # Covert to datetime and filter
    df["ContributionDate"] = pd.to_datetime(df["ContributionDate"], errors="coerce")
    df = df[
        (df["ContributionDate"] >= contribution_start)
        & (df["ContributionDate"] <= contribution_end)
    ].reset_index(drop=True)

    df["Amount"] = clean_amount(df["Amount"])

    # ----------------------------------------------
    # FIX CONTRIBUTOR TYPES and NAME
    # ----------------------------------------------

    # fills blank contribution type with Unknown, set Pac to PAC
    df["ContributorType"] = (
        df["ContributorType"]
        .replace(r"^\s*$", pd.NA, regex=True)
        .replace("Not Provided", pd.NA)
        .fillna("(Unknown)")
        .str.replace("Pac", "PAC")
    )
    df.rename(columns={"ContributorType":"Contributor Type"}, inplace=True)

    # clean contributor name - combine first name/last name for individuals 
    # and NonIndName for companies
    df.loc[df["IsIndividual"]=="Y","ContributorName"] = (
        df.loc[df["IsIndividual"]=="Y","FirstName"].fillna("")+
        " "+
        df.loc[df["IsIndividual"]=="Y","LastName"].fillna("")
    )
    df.loc[df["IsIndividual"]=="N","ContributorName"] = (
        df.loc[df["IsIndividual"]=="N","NonIndName"].fillna("")
        # make LLC and LLPs uppercase
        .str.replace("Llp", "LLP")
        .str.replace("Llc", "LLC")
        # fix PAC name
        .str.replace("Pac", "PAC")
    )

    # ----------------------------------------------
    # SUMMARIZE DATA
    # ----------------------------------------------

    # total contributions
    summary = (
<<<<<<< HEAD
        df2.groupby(["CandidateID", "Candidate", 'Location', 'Office'], dropna=False)
        .agg(
            **{
             "Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")
             }
    ) ).reset_index(drop = False)
    summary['Total Contributions'] = round_amount(summary['Total Contributions'] )
    
    # ADD KISHA SKIPPER 
    #summary = pd.concat([pd.DataFrame({'CandidateID': 2,
    #    'Candidate': 'Kisha Skipper (D)', 
    #                         'Location': '15th District', 
    #                         'Office': 'County Legislator', 
    #                         'Total Contributions': 0}, index = [0]), 
    #           summary], axis = 0)
    
    # ADD Thomas Fix Jr.
    summary = pd.concat([pd.DataFrame({'CandidateID': 2,
        'Candidate': 'Thomas Fix Jr. (R)', 
                             'Location': '37th District', 
                             'Office': 'State Senate', 
                             'Total Contributions': 0}, index = [0]), 
               summary], axis = 0)
    
=======
        df.groupby(
            ["CandidateID", "Candidate", "Location", "Office"], dropna=False
        ).agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
    ).reset_index(drop=False)
    summary["Total Contributions"] = round_amount(summary["Total Contributions"])
>>>>>>> nj-development


    # contributor type
    contrib_summary = (
        df.groupby(["CandidateID", "Candidate", "Contributor Type"], dropna=False).agg(
            **{
                "Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum"),
                "Number of Contributions": pd.NamedAgg(
                    column="Amount", aggfunc="count"
                ),
            }
        )
    ).reset_index(drop=False)

    contrib_summary["Total Contributions"] = round_amount(
        contrib_summary["Total Contributions"]
    )

    # top contributors grouped by cleaned name and cleaned city
    donor_summary = (
        df.groupby(
            [
                "CandidateID",
                "Candidate",
                "ContributorName",
            ],
            dropna=False,
        )
        .agg(
            **{
                "Contributor Type": pd.NamedAgg(
                    column="Contributor Type",
                    aggfunc=lambda x: " | ".join(
                        pd.Series(x.dropna().astype(str).unique()).sort_values()
                    ),
                ),
                "Contributor Name": pd.NamedAgg(
                    column="ContributorName",
                    aggfunc=lambda x: " | ".join(
                        pd.Series(x.dropna().astype(str).unique()).sort_values()
                    ),
                ),
                "Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum"),
                "Number of Contributions": pd.NamedAgg(
                    column="Amount", aggfunc="count"
                ),
            }
        )
        .sort_values(
            ["Total Contributions", "Contributor Name"], ascending=False
        )  # sort by amount and name to keep top 10 list stable
        .groupby(["CandidateID", "Candidate"], group_keys=False)
        .apply(lambda g: g.nlargest(10, "Total Contributions"))
        .reset_index(drop=False)
        .drop(columns=["Contributor Name"])
    )

    donor_summary["Total Contributions"] = round_amount(
        donor_summary["Total Contributions"]
    )

    # pac contributors
    pacs = df[
        df["Contributor Type"]
        .str.strip()
        .str.lower()
        .str.contains("pac|political action committee")
    ]
    pacs_summary = (
        pacs.groupby(["CandidateID", "Candidate", "ContributorName"])
        .agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
        .groupby(["CandidateID", "Candidate"], group_keys=False)
        # sort by amount and name to keep list stable
        .apply(
            lambda x: x.sort_values(
                ["Total Contributions", "ContributorName"], ascending=False
            )
        )
    ).reset_index(drop=False)

    pacs_summary["Total Contributions"] = round_amount(
        pacs_summary["Total Contributions"]
    )

    # corporate contributors
<<<<<<< HEAD
    corporates = df2[df2['Contributor Type'].str.strip().str.lower().str.contains("partnership|professional|limited liability company")]
    corporates_summary = (corporates.groupby(["CandidateID", "Candidate", "Contributor Name"])
                   .agg(
                       **{
                        "Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")
                        })                   
                   .groupby(["CandidateID", "Candidate"], group_keys=False)
        .apply(lambda x: x.sort_values(["Total Contributions", "Contributor Name"], ascending=False) ) ).reset_index(drop = False)
    
    corporates_summary['Total Contributions'] = round_amount(corporates_summary['Total Contributions'] )
    
    
    # ----------------------------------------------------------------
    # STATE CONTRIBUTIONS
    # ----------------------------------------------------------------
    
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
    "Puerto Rico": "PR"
}
    
    
    state_lookup = {k.lower(): v for k, v in states.items()}
    
    # for states names spelled out, match with state abbreviation. For those without state names, fill with contributor state 
    df2['Contributor State_clean'] = df2["Contributor State"].str.strip().str.lower().map(state_lookup).fillna(df2["Contributor State"])
    
    df2['Contributor State_clean'] = df2['Contributor State_clean'].str.strip().str.lower()
    
    
    df2['Contributor Location'] = np.where(df2['Contributor State_clean'] ==state, "In-state", "Out-of-state")
    df2['Contributor Location']  = np.where(df2['Contributor State_clean'].isna()==True, "Undisclosed", df2['Contributor Location'])
 
    instate_contr = df2.groupby(['CandidateID', 'Candidate', 'Contributor Location'])['Amount'].sum().reset_index(drop = False)
    state_contr = df2.groupby(['CandidateID', 'Candidate', 'Contributor State_clean'])['Amount'].sum().reset_index(drop = False)
    state_contr['Contributor State_clean'] = state_contr['Contributor State_clean'].str.upper()
    state_contr = state_contr.rename({'Contributor State_clean': 'State'}, axis = 1)
    
    
=======
    corporates = df[
        df["Contributor Type"]
        .str.strip()
        .str.lower()
        .str.contains("business/corp")
    ]
    corporates_summary = (
        corporates.groupby(["CandidateID", "Candidate", "ContributorName"])
        .agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
        .groupby(["CandidateID", "Candidate"], group_keys=False)
        .apply(
            lambda x: x.sort_values(
                ["Total Contributions", "ContributorName"], ascending=False
            )
        )
    ).reset_index(drop=False)

    corporates_summary["Total Contributions"] = round_amount(
        corporates_summary["Total Contributions"]
    )


>>>>>>> nj-development
    # parmeters to show on UI
    parameters = pd.DataFrame(
        {
            "Newsroom": newsroom,
            "State": state.upper(),
            "Data Start": contribution_start,
            "Data End": contribution_end,
        },
        index=[0],
    )

    # export csvs
    output_dir.mkdir(exist_ok=True)

    summary.to_csv(output_dir / "total_contributions.csv", index=False)
    contrib_summary.to_csv(output_dir / "contributor_types.csv", index=False)
    donor_summary.to_csv(output_dir / "top_contributors.csv", index=False)
    pacs_summary.to_csv(output_dir / "pac_contributors.csv", index=False)
    corporates_summary.to_csv(
        output_dir / "corporate_contributors.csv", index=False
    )
    parameters.to_csv(output_dir / "parameters.csv", index=False)


if __name__ == "__main__":
    main()
