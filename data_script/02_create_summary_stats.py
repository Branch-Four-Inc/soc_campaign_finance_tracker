# -*- coding: utf-8 -*-
"""
Created on Wed Aug 19 21:08:52 2026

@author: stm4z
"""

import pandas as pd 
import numpy as np 
import os


input_dir = './data_output/HUDSON COUNTY/'



def top_two_spread(group: pd.DataFrame): 
    
    ''' 
    Calculate election with widest fundraising gap
    '''
    sorted_group = group.sort_values('Total Contributions', ascending=False)
    top_row = sorted_group.iloc[0]
    
    # Handle groups with only one candidate
    if len(sorted_group) > 1:
        second_row = sorted_group.iloc[1]
        second_candidate = second_row['Candidate']
        second_value = second_row['Total Contributions']
        difference = top_row['Total Contributions'] - second_value
    else:
        second_candidate = None
        second_value = None
        difference = None  # or 0, depending on how you want to treat single-candidate groups
    
    return pd.Series({
        'Highest Candidate': top_row['Candidate'],
        'Highest Contributions': top_row['Total Contributions'],
        'Second Highest Candidate': second_candidate,
        'Second Highest Contributions': second_value,
        'Difference': difference
    })


def top_candidate(df: pd.DataFrame, 
                  variable: str, 
                  contains_string: str, 
                  sorting_variable: str):
    
    ''' 
    Identify top candidate for different money categories 
    '''
    
    return (df[df[variable].str.lower().str.contains(contains_string)]
                      .sort_values(sorting_variable, ascending = False)
                      .head(1) )
    


pac_string = 'pac|political action committee'
corporate_string = 'business|corp'
outstate_string = 'out-of-state'
union_string = 'union'



total_contributions = pd.read_csv(input_dir + 'total_contributions.csv')

# Total contribution by election
total_contributions_by_election = (total_contributions.groupby(['Location', 'Office'])['Total Contributions']
                                   .sum()
                                   .reset_index(drop=False)
                                   .sort_values(['Location', 'Office']))


# ------------------------------------------------------------------------------------------
# MOST BY MONEY 
# ------------------------------------------------------------------------------------------

# most pac money 
contributor_type = pd.read_csv(input_dir + 'contributor_types.csv')

most_pac_money = top_candidate(contributor_type, 'Contributor Type', pac_string, 'Total Contributions')

# most corporate 
most_corporate_money = top_candidate(contributor_type, 'Contributor Type', corporate_string, 'Total Contributions')


# most out of state 
in_state = pd.read_csv(input_dir + 'instate_perc.csv')

most_out_state_money = top_candidate(in_state, 'Contributor Location', outstate_string, 'Amount')


# widest fundraising gap

#fundraising_gap = total_contributions.groupby(['Location', 'Office']).apply(top_two_spread, include_groups=False).reset_index().sort_values('Difference', ascending=False)
#fundraising_gap =  total_contributions.groupby(['Location', 'Office']).apply(top_two_spread).reset_index().sort_values('Difference', ascending = False)

fundraising_gap = (
    total_contributions
    .groupby(['Location', 'Office'], group_keys=False)
    .apply(top_two_spread)
    .dropna(subset=['Difference'])
    .sort_values('Difference', ascending=False)
)
widest_gap = fundraising_gap.head(1)
smallest_gap = fundraising_gap.tail(1)

# top fundraiser 
top_fundraiser = total_contributions.sort_values('Total Contributions', ascending=False).head(1)


# ------------------------------------------------------------------------------------------
# MOST BY SHARE
# ------------------------------------------------------------------------------------------

# HIGHEST SHARE BY PAC, CORPORATE, UNION 

contribution_share = contributor_type.merge(total_contributions[['Candidate', 'Total Contributions']], how = 'left', on = 'Candidate')
contribution_share['share'] = contribution_share['Total Contributions_x']/contribution_share['Total Contributions_y']

# pac share 
pac_share = top_candidate(contribution_share, 'Contributor Type', pac_string, 'share')

# corporate share 
corporate_share =  top_candidate(contribution_share, 'Contributor Type', corporate_string, 'share')

# union share 
union_share = top_candidate(contribution_share, 'Contributor Type', union_string, 'share')

# HIGHEST OUT OF STATE SHARE

state_share = in_state.merge(total_contributions[['Candidate', 'Total Contributions']], how = 'left', on = 'Candidate')
state_share['share'] = state_share['Amount']/state_share['Total Contributions']

outstate_share = top_candidate(state_share, 'Contributor Location', outstate_string, 'share')


# ------------------------------------------------------------------------------------------
# EXPORT OUTPUTS 
# ------------------------------------------------------------------------------------------

if not os.path.exists(input_dir + '//summary_page'):
    os.makedirs(input_dir + '//summary_page')

# output totals 
total_contributions_by_election.to_csv(input_dir + 'summary_page//total_contributions_by_election.csv')
most_pac_money.to_csv(input_dir + 'summary_page//most_pac_money.csv')
most_corporate_money.to_csv(input_dir + 'summary_page//most_corporate_money.csv')
most_out_state_money.to_csv(input_dir + 'summary_page//most_out_state_money.csv')
widest_gap.to_csv(input_dir + 'summary_page//widest_fundraising_gap.csv')
smallest_gap.to_csv(input_dir + 'summary_page//smallest_fundraising_gap.csv')

# output shares 
pac_share.to_csv(input_dir + 'summary_page//most_pac_share.csv')
corporate_share.to_csv(input_dir + 'summary_page//most_corporate_share.csv')
union_share.to_csv(input_dir + 'summary_page//most_union_share.csv')
outstate_share.to_csv(input_dir + 'summary_page//most_out_state_share.csv')
