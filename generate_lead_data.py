"""
Module 5a - Synthetic B2B Lead Data Generator

Remaps the Kaggle 'Lead Scoring.csv' (education leads) to a B2B schema,
then trains CTGAN to generate ~20k multi-industry synthetic leads.

Output files:
  - b2b_leads_remapped.csv  (intermediate, ~9k rows)
  - b2b_leads_synthetic.csv (final, ~20k rows)
"""

import pandas as pd
import numpy as np
import random
import string
import os

# ---- Configuration ----

INPUT_CSV = "Lead Scoring.csv"
OUTPUT_CSV = "b2b_leads_synthetic.csv"
REMAPPED_CSV = "b2b_leads_remapped.csv"
ROWS_PER_INDUSTRY = 2000

INDUSTRIES = [
    "SaaS", "Consulting", "Manufacturing", "Logistics & Supply Chain",
    "Healthcare Services", "Fintech", "Retail Technology",
    "Construction", "Education Technology", "Professional Services",
]

JOB_TITLES = [
    "CEO", "CTO", "CFO", "COO", "VP Sales", "VP Marketing",
    "Director of IT", "Director of Operations", "Procurement Manager",
    "Head of Partnerships", "Business Development Manager",
    "Sales Manager", "Marketing Manager", "Product Manager",
    "General Manager", "Managing Director", "Founder",
    "IT Manager", "Chief Strategy Officer", "Account Executive",
]

EMPLOYEE_BUCKETS = ["1-50", "51-200", "201-1000", "1000+"]
REVENUE_RANGES = ["<$1M", "$1-10M", "$10-50M", ">$50M"]

COMPANY_PREFIXES = [
    "Alpha", "Beta", "Summit", "Apex", "Nova", "Peak", "Vertex", "Horizon",
    "Pinnacle", "Prime", "Core", "Nexus", "Atlas", "Titan", "Stellar",
    "Quantum", "Vanguard", "Catalyst", "Eagle", "Emerald", "Falcon",
    "Phoenix", "Orion", "Pacific", "Global", "Metro", "Coastal", "Sierra",
    "Nordic", "Sapphire", "Ironclad", "Redwood", "Sterling", "Crescent",
]

COMPANY_SUFFIXES = [
    "Solutions", "Technologies", "Systems", "Group", "Corp", "Industries",
    "Dynamics", "Ventures", "Partners", "Services", "Labs", "Digital",
    "Holdings", "International", "Analytics", "Innovations", "Consulting",
    "Enterprises", "Works", "Software",
]

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


# ---- Helpers ----

def generate_company_name():
    return f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"


def generate_email(company_name, job_title):
    first_names = ["james", "sarah", "mike", "anna", "david", "priya", "chen", "omar", "alex", "maria"]
    last_names = ["smith", "patel", "johnson", "lee", "khan", "wilson", "garcia", "mueller", "tanaka", "singh"]
    domain = company_name.lower().replace(" ", "").replace("&", "")[:12]
    tlds = [".com", ".io", ".co", ".tech", ".biz"]
    name = f"{random.choice(first_names)}.{random.choice(last_names)}"
    return f"{name}@{domain}{random.choice(tlds)}"


def map_occupation_to_job_title(occupation):
    mapping = {
        "Working Professional": random.choice(["VP Sales", "Director of Operations", "Business Development Manager", "Sales Manager", "Marketing Manager"]),
        "Unemployed": random.choice(["Founder", "CEO", "Managing Director", "Consultant"]),
        "Student": random.choice(["Account Executive", "Business Development Manager", "Junior Analyst"]),
        "Businessman": random.choice(["CEO", "Founder", "Managing Director", "COO"]),
        "Housewife": random.choice(["Founder", "CEO", "Freelance Consultant"]),
        "Other": random.choice(JOB_TITLES),
    }
    return mapping.get(occupation, random.choice(JOB_TITLES))


def assign_employee_bucket(job_title):
    senior_titles = ["CEO", "CTO", "CFO", "COO", "Founder", "Managing Director", "VP Sales", "VP Marketing"]
    if job_title in senior_titles:
        return random.choice(["1-50", "1-50", "51-200", "1000+"])
    return random.choice(EMPLOYEE_BUCKETS)


def assign_revenue_range(employee_bucket):
    correlations = {
        "1-50": ["<$1M", "<$1M", "$1-10M"],
        "51-200": ["$1-10M", "$1-10M", "$10-50M"],
        "201-1000": ["$10-50M", "$10-50M", ">$50M"],
        "1000+": ["$10-50M", ">$50M", ">$50M"],
    }
    return random.choice(correlations.get(employee_bucket, REVENUE_RANGES))


# ---- Phase 1: Remap CSV ----

def remap_csv(input_path: str) -> pd.DataFrame:
    """
    Load the Kaggle CSV, drop education-specific columns, rename
    salvageable ones, and fill in synthetic B2B columns.
    """
    df = pd.read_csv(input_path)
    print(f"Loaded {input_path} ({df.shape[0]} rows, {df.shape[1]} cols)")

    remapped = pd.DataFrame()
    remapped["Converted"] = df["Converted"]

    # Country - replace "Select" / NaN with a random B2B country
    remapped["Country"] = df["Country"].apply(
        lambda x: x if isinstance(x, str) and x not in ["Select", ""] else random.choice(COUNTRIES_B2B)
    )
    remapped["Country"] = remapped["Country"].fillna(
        remapped["Country"].apply(lambda _: random.choice(COUNTRIES_B2B))
    )

    # City - replace "Select" / NaN, derive from assigned country
    def clean_city(row):
        city = df.at[row.name, "City"] if "City" in df.columns else None
        if pd.isna(city) or city in ["Select", ""]:
            return random.choice(CITIES_BY_COUNTRY.get(row["Country"], ["Unknown"]))
        return city

    remapped["City"] = remapped.apply(clean_city, axis=1)

    # Job title - remap from occupation column
    occ_col = "What is your current occupation"
    if occ_col in df.columns:
        remapped["Decision_Maker_Job_Title"] = df[occ_col].apply(
            lambda x: map_occupation_to_job_title(x) if isinstance(x, str) else random.choice(JOB_TITLES)
        )
    else:
        remapped["Decision_Maker_Job_Title"] = [random.choice(JOB_TITLES) for _ in range(len(df))]


    # Synthetic columns
    remapped["Industry"] = [random.choice(INDUSTRIES) for _ in range(len(df))]
    remapped["Company_Name"] = [generate_company_name() for _ in range(len(df))]
    remapped["Email"] = remapped.apply(
        lambda row: generate_email(row["Company_Name"], row["Decision_Maker_Job_Title"]), axis=1
    )
    remapped["Employee_Count"] = remapped["Decision_Maker_Job_Title"].apply(assign_employee_bucket)
    remapped["Annual_Revenue_Range"] = remapped["Employee_Count"].apply(assign_revenue_range)

    # Final column order
    remapped = remapped[[
        "Company_Name", "Email", "Decision_Maker_Job_Title",
        "Industry", "Country", "City", "Employee_Count",
        "Annual_Revenue_Range", "Converted"
    ]]

    print(f"Remapped to {remapped.shape[1]} columns, conversion rate: {remapped['Converted'].mean():.2%}")
    return remapped


# ---- Phase 2: CTGAN Synthetic Generation ----

def generate_synthetic_data(remapped_df: pd.DataFrame, output_path: str):
    """
    Train CTGAN on the remapped data, then sample 2k rows per industry.
    """
    try:
        from sdv.single_table import CTGANSynthesizer
        from sdv.metadata import SingleTableMetadata
    except ImportError:
        print("SDV not installed. Run: pip install sdv")
        return

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(remapped_df)
    metadata.update_column(column_name="Converted", sdtype="categorical")
    metadata.update_column(column_name="Email", sdtype="email")

    print("Training CTGAN (300 epochs)...")
    synthesizer = CTGANSynthesizer(metadata, epochs=300, batch_size=500, verbose=True)
    synthesizer.fit(remapped_df)

    all_synthetic = []
    for industry in INDUSTRIES:
        print(f"  Sampling {ROWS_PER_INDUSTRY} rows for {industry}")
        synthetic = synthesizer.sample(num_rows=ROWS_PER_INDUSTRY)
        synthetic["Industry"] = industry
        synthetic["Company_Name"] = [generate_company_name() for _ in range(len(synthetic))]
        synthetic["Email"] = synthetic.apply(
            lambda row: generate_email(row["Company_Name"], row["Decision_Maker_Job_Title"]), axis=1
        )
        all_synthetic.append(synthetic)

    final_df = pd.concat(all_synthetic, ignore_index=True)
    final_df["Converted"] = final_df["Converted"].astype(int).clip(0, 1)

    print(f"Generated {len(final_df)} rows, conversion rate: {final_df['Converted'].mean():.2%}")
    print(f"Industry distribution:\n{final_df['Industry'].value_counts().to_string()}")

    final_df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
    return final_df


# ---- Main ----

if __name__ == "__main__":
    remapped = remap_csv(INPUT_CSV)
    remapped.to_csv(REMAPPED_CSV, index=False)
    print(f"Saved intermediate file: {REMAPPED_CSV}\n")

    generate_synthetic_data(remapped, OUTPUT_CSV)
