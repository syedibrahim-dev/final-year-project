"""
Module 5a - Post-process CTGAN output

Fixes three known issues in the synthetic data:
  1. City - replace hallucinated names with valid cities from our vocabulary
  2. Industry - inject differentiated conversion rates per industry
  3. Country - clamp to our original 10-country list

Run after generate_lead_data.py, before training the XGBoost model.
"""

import pandas as pd
import numpy as np
import random

INPUT_CSV = "b2b_leads_synthetic.csv"
OUTPUT_CSV = "b2b_leads_final.csv"

COUNTRIES_B2B = [
    "India", "United States", "United Kingdom", "UAE", "Singapore",
    "Germany", "Australia", "Canada", "Netherlands", "Saudi Arabia",
]

CITIES_BY_COUNTRY = {
    "India": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Pune", "Chennai"],
    "United States": ["New York", "San Francisco", "Chicago", "Austin", "Seattle", "Boston"],
    "United Kingdom": ["London", "Manchester", "Birmingham", "Edinburgh"],
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah"],
    "Singapore": ["Singapore"],
    "Germany": ["Berlin", "Munich", "Frankfurt", "Hamburg"],
    "Australia": ["Sydney", "Melbourne", "Brisbane"],
    "Canada": ["Toronto", "Vancouver", "Montreal"],
    "Netherlands": ["Amsterdam", "Rotterdam", "The Hague"],
    "Saudi Arabia": ["Riyadh", "Jeddah", "Dammam"],
}

# Target conversion rates per industry to inject meaningful signal.
# These reflect realistic B2B patterns: tech/consulting convert higher,
# construction/manufacturing convert lower.
INDUSTRY_CONVERSION_RATES = {
    "SaaS": 0.35,
    "Fintech": 0.32,
    "Education Technology": 0.30,
    "Consulting": 0.28,
    "Professional Services": 0.27,
    "Retail Technology": 0.25,
    "Healthcare Services": 0.22,
    "Logistics & Supply Chain": 0.20,
    "Manufacturing": 0.17,
    "Construction": 0.14,
}


def fix_countries(df):
    """Clamp countries to our predefined list."""
    valid = set(COUNTRIES_B2B)
    invalid_mask = ~df["Country"].isin(valid)
    n_fixed = invalid_mask.sum()

    df.loc[invalid_mask, "Country"] = [
        random.choice(COUNTRIES_B2B) for _ in range(n_fixed)
    ]
    print(f"Country: fixed {n_fixed} invalid values")
    return df


def fix_cities(df):
    """Replace all cities with valid ones derived from the row's country."""
    all_valid_cities = set()
    for cities in CITIES_BY_COUNTRY.values():
        all_valid_cities.update(cities)

    invalid_mask = ~df["City"].isin(all_valid_cities)
    n_fixed = invalid_mask.sum()

    df.loc[invalid_mask, "City"] = df.loc[invalid_mask, "Country"].apply(
        lambda c: random.choice(CITIES_BY_COUNTRY.get(c, ["Unknown"]))
    )
    print(f"City: fixed {n_fixed} invalid values ({df['City'].nunique()} unique cities remaining)")
    return df


def fix_industry_conversion(df):
    """
    Re-assign Converted labels per industry to match target rates.
    
    For each industry group, we sort rows by a composite 'propensity'
    derived from the existing feature values (so conversions still
    correlate with job title, revenue, etc.) and then set the top N%
    as converted based on the target rate.
    """
    # Build a simple propensity score from existing features
    # so that conversions aren't randomly assigned
    title_weights = {
        "CEO": 0.7, "Founder": 0.7, "Managing Director": 0.65,
        "CTO": 0.6, "CFO": 0.55, "COO": 0.55,
        "VP Sales": 0.5, "VP Marketing": 0.5,
        "Director of IT": 0.45, "Director of Operations": 0.45,
        "Head of Partnerships": 0.4, "Business Development Manager": 0.4,
        "Sales Manager": 0.35, "Marketing Manager": 0.35,
        "Product Manager": 0.35, "General Manager": 0.3,
        "IT Manager": 0.3, "Chief Strategy Officer": 0.5,
        "Account Executive": 0.25, "Procurement Manager": 0.2,
        "Freelance Consultant": 0.3, "Consultant": 0.35,
        "Junior Analyst": 0.15,
    }
    revenue_weights = {">$50M": 0.4, "$10-50M": 0.3, "$1-10M": 0.2, "<$1M": 0.1}
    size_weights = {"1000+": 0.3, "201-1000": 0.25, "51-200": 0.2, "1-50": 0.15}

    df["_propensity"] = (
        df["Decision_Maker_Job_Title"].map(title_weights).fillna(0.3)
        + df["Annual_Revenue_Range"].map(revenue_weights).fillna(0.2)
        + df["Employee_Count"].map(size_weights).fillna(0.2)
        + np.random.uniform(0, 0.3, size=len(df))  # noise to avoid deterministic ties
    )

    new_converted = df["Converted"].copy()

    for industry, target_rate in INDUSTRY_CONVERSION_RATES.items():
        mask = df["Industry"] == industry
        group = df[mask].sort_values("_propensity", ascending=False)
        n_total = len(group)
        n_positive = int(n_total * target_rate)

        # Top propensity rows convert, rest don't
        positive_idx = group.index[:n_positive]
        negative_idx = group.index[n_positive:]
        new_converted.loc[positive_idx] = 1
        new_converted.loc[negative_idx] = 0

    df["Converted"] = new_converted.astype(int)
    df.drop(columns=["_propensity"], inplace=True)

    # Verify
    rates = df.groupby("Industry")["Converted"].mean().sort_values(ascending=False)
    print(f"Industry conversion rates after fix:")
    for ind, rate in rates.items():
        target = INDUSTRY_CONVERSION_RATES[ind]
        print(f"  {ind}: {rate:.1%} (target: {target:.0%})")

    return df


def main():
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows\n")

    df = fix_countries(df)
    df = fix_cities(df)
    df = fix_industry_conversion(df)

    print(f"\nOverall conversion rate: {df['Converted'].mean():.2%}")
    print(f"Final shape: {df.shape}")

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
