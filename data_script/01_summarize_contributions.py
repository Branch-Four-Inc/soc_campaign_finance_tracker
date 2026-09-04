import numpy as np
import pandas as pd
from pathlib import Path
from utils import round_amount, clean_amount



def main(file_format="tsv",):

    ############# CONFIG ##########################
    county = "HUDSON COUNTY"
    contribution_start = "2020-01-01"
    newsroom = "Slice of Culture"
    pull_date = "2026-09-04"
    contribution_end = pull_date
    state = "NJ"
    ###############################################

    input_dir = Path(f"raw_contributions/{county}")
    output_dir = Path(f"data_output/{county}")
    candidate_info_dir = input_dir / Path(f"candidates_{'_'.join(county.split(' '))}_2026.tsv")
    file_names = input_dir.glob(f"*{file_format}")

    df_list = []

    # read in all files into one list
    for f in file_names:
        # read all files not including candidate info
        if "candidates_" not in str(f):
            try:
                temp_df = (
                    pd.read_csv(f, index_col=False, delimiter="\t")
                    .rename(columns={
                        "ENTITY_S":"CandidateID",
                        "CONT_AMT":"Amount",
                        "CONT_DATE":"ContributionDate",
                        "CONTRIBUTOR": "ContributorName"
                    })
                    # remove any duplicate contributions
                    .drop_duplicates().reset_index(drop=True)
                )
                df_list += [temp_df]
            except Exception as e:
                # Most of these are issues with commas in names
                raise ValueError(e)

    contributions = pd.concat(df_list, ignore_index=True)

    # ----------------------------------------------
    # LOAD IN CANDIDATE INFO
    # ----------------------------------------------

    cand_info = (
        pd.read_csv(candidate_info_dir, delimiter="\t")
        .rename(columns={
            "name": "Candidate",
            "office_cmte": "Office",
            # "election_type": "Election",
            "eid":"CandidateID",
            "party": "Party",
            "location":"Location"
        })
        # .drop_duplicates(["Candidate"])
        .drop(columns=["search_location"])
        .sort_values(["Office", "Candidate"])
        .reset_index(drop=True)
    )

    # Clean up the names so that we're grouping the primary and general elections together
    # have to do this manually
    HC_NAME_MAPPING = {"BAUTISTA, RON": "BAUTISTA, RONALD"}
    EC_NAME_MAPPING = {
        "DIVINCENZO, JOSEPH N JR": "DIVINCENZO, JOSEPH",
        "MATHEWS, MARITIZA": "MATHEWS, MARITZA",
        "MURRAY-THOMAS, ADORIAN": "MURRAY-THOMAS, A'DORIAN",
        "POMARES, CARLOS  M": "POMARES, CARLOS"
    }
    CNTY_MAP = {"HUDSON COUNTY": HC_NAME_MAPPING, "ESSEX COUNTY": EC_NAME_MAPPING}
    cand_info["Candidate"] = cand_info["Candidate"].replace(CNTY_MAP[county])
    # if we end up wanting to combine the contributions for individuals to the committees
    # HC_CMTE_MAPPING = {
    #         503036: [459096, 441534, 503034, 503035, 502893, 446426],
    #         502842: [502840, 502841, 502937, 502938, 505544, 503283, 505610, 502634]
    #     }
    # EC_CMTE_MAPPING = {
    #     437005: [503419, 437003, 437004, 437001], 
    #     505387: [504072, 507886, 503605, 508277, 461343, 507889, 505885, 460962, 503423, 502949, 505886, 459513, 507881, 503394, 507880]
    # }

    # There are multiple rows for the same candidate based on primary vs full election,
    # so need to merge on ID and then sum across Candidate name
    all_info = pd.merge(contributions, cand_info, on="CandidateID", how="outer")

    # Group and sum to collapse GENERAL and PRIMARY
    no_grp = ["election_type", "Amount", "CandidateID", "STREET1", "STREET2"]
    agg_cols = [col for col in all_info.columns if col not in no_grp]
    df = all_info.groupby(agg_cols, as_index=False)["Amount"].sum()

    # Manually add back candidates with no contributions
    total_cont = all_info.groupby("Candidate")["Amount"].sum()
    zero = total_cont[total_cont == 0].index.to_list()
    df = pd.concat([df, all_info.loc[all_info["Candidate"].isin(zero), df.columns]])
    df["Amount"] = df["Amount"].fillna(0)

    # ----------------------------------------------
    # ADD EXTRA COLUMNS, CLEAN STRINGS
    # ----------------------------------------------
    # hard-coded for now, as all data was pulled the same day
    df["PullDate"] = pull_date

    # if there is 'Union' or 'PAC' or 'LLC' in the Contributor's name, switch it to not being an individual
    df.loc[(df["IsIndividual"]=="Y") & (df["ContributorName"].str.contains("UNION|LLC|CORP|PAC")),"IsIndividual"] = "N"

    # Clean up the values for candidates, individuals, location, etc.
    title_cols = [
        # Candidate columns
        "Candidate",
        "Location",
        "Office",
        "Party",
        # Contributor columns
        "ContributorName",
        "ContributorType",
    ]
    df.loc[:, title_cols] = df.loc[:, title_cols].apply(lambda x: x.str.strip().str.title())

    # Covert to datetime and filter
    df["ContributionDate"] = pd.to_datetime(df["ContributionDate"], errors="coerce").fillna(pd.to_datetime(pull_date))
    df = df[
        (df["ContributionDate"] >= contribution_start)
        & (df["ContributionDate"] <= contribution_end)
    ].reset_index(drop=True)

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
    df.rename(columns={"ContributorType": "Contributor Type"}, inplace=True)

    # clean contributor name
    df.loc[df["IsIndividual"]=="N","ContributorName"] = (
        df.loc[df["IsIndividual"]=="N","ContributorName"].fillna("")
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
        df.groupby(
            ["Candidate", "Location", "Office"], dropna=False
        ).agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
    ).reset_index(drop=False)
    summary["Total Contributions"] = round_amount(summary["Total Contributions"])

    breakpoint()

    # contributor type
    contrib_summary = (
        df.groupby(["Candidate", "Contributor Type"], dropna=False).agg(
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
        .groupby(["Candidate"], group_keys=False)
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
        pacs.groupby(["Candidate", "ContributorName"])
        .agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
        .groupby(["Candidate"], group_keys=False)
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
    corporates = df[
        df["Contributor Type"]
        .str.strip()
        .str.lower()
        .str.contains("business/corp")
    ]
    corporates_summary = (
        corporates.groupby(["Candidate", "ContributorName"])
        .agg(**{"Total Contributions": pd.NamedAgg(column="Amount", aggfunc="sum")})
        .groupby(["Candidate"], group_keys=False)
        .apply(
            lambda x: x.sort_values(
                ["Total Contributions", "ContributorName"], ascending=False
            )
        )
    ).reset_index(drop=False)

    corporates_summary["Total Contributions"] = round_amount(
        corporates_summary["Total Contributions"]
    )

    # ----------------------------------------------------------------
    # STATE CONTRIBUTIONS
    # ----------------------------------------------------------------
    df['Contributor Location'] = np.where(df['STATE'] == state, "In-state", "Out-of-state")
    df['Contributor Location'] = np.where(df['STATE'].isna()==True, "Undisclosed", df['Contributor Location'])
    
    instate_contr = df.groupby(['Candidate', 'Contributor Location'])['Amount'].sum().reset_index(drop = False)
    state_contr = df.groupby(['Candidate', 'STATE'])['Amount'].sum().reset_index(drop = False)
    # state_contr['STATE'] = state_contr['STATE'].str.upper()
    state_contr = state_contr.rename({'STATE': 'State'}, axis = 1)


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
    instate_contr.to_csv(output_dir / 'instate_perc.csv', index = False)
    state_contr.to_csv(output_dir / 'all_state_perc.csv', index = False)


if __name__ == "__main__":
    main()
