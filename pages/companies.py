import streamlit as st
import pandas as pd
import uuid
from fuzzywuzzy import process
import unidecode
from urllib.request import Request, urlopen


# Function to convert the Google Sheets into a CSV link
def convert_to_csv_url(view_url):
    # Extract file ID and gid
    file_id = view_url.split('/')[5]  # Extract file ID from URL
    gid = view_url.split('gid=')[-1]  # Extract gid parameter
    # Build export URL
    return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"


# Function to load the remote dataset and filter by country
@st.cache_data
def load_remote_dataset(country):
    url = 'https://soe-database.eiti.org/eiti_database/companies.csv?_size=max'
    req = Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0')
    content = urlopen(req)

    remote_df = pd.read_csv(content)
    filtered_df = remote_df[remote_df['country'].str.upper() == country.upper()]
    unique_companies = filtered_df.drop_duplicates(subset=['eiti_id_company'])
    return unique_companies


# Function to generate UUID4
def generate_uuid():
    return str(uuid.uuid4())


# Function to preprocess text (convert to uppercase and remove diacritics)
def preprocess_text(text):
    return unidecode.unidecode(text).upper()


# Function to preprocess the new data
def preprocess_dataset(df):
    df['Company'] = df['Company'].apply(preprocess_text)
    return df


# Function to get potential matches using fuzzy matching
def get_potential_matches(unmatched_series, remote_column):
    potential_matches = unmatched_series.apply(lambda x: process.extractOne(x, remote_column)[0])
    return potential_matches


# Function to display unmatched entities with potential matches
def display_unmatched(unmatched_df, remote_df, entity_type, remote_column):
    st.subheader(f"Unmatched {entity_type.capitalize()}s")
    for index, row in unmatched_df.iterrows():
        unmatched_df.at[index, 'Potential_Match'] = st.selectbox(
            f"Potential Match for {row[entity_type]}",
            options=['No potential match'] + remote_df[remote_column].tolist(),
            key=f"{entity_type}_match_{index}"
        )
        if unmatched_df.at[index, 'Potential_Match'] != 'No potential match':
            unmatched_df.at[index, 'EITI ID'] = remote_df[remote_df[remote_column] == unmatched_df.at[index, 'Potential_Match']][f'eiti_id_{entity_type.split()[0].lower()}'].values[0]
    st.dataframe(unmatched_df)


# Function to validate and finalize matching
def validate_matching(df, company_matches, unmatched_companies):
    # Fill missing EITI IDs in unmatched_companies
    unmatched_companies['EITI ID'] = unmatched_companies['EITI ID'].replace('', pd.NA).fillna(generate_uuid())
    unmatched_mapping = unmatched_companies.drop_duplicates(subset=['Company']).set_index('Company')['EITI ID']

    # Merge existing matches
    df = pd.merge(df, company_matches[['Company', 'eiti_id_company']], on='Company', how='left')
    # Map unmatched companies
    df['eiti_id_company'] = df['eiti_id_company'].fillna(df['Company'].map(unmatched_mapping))
    return df


companies_page = st.Page("./pages/companies.py", title="Companies", icon=":material/add_circle:")


# Main function to run the Streamlit app
def page():
    st.header("Company entities")

    # SECTION 1: Input Google Sheet URL
    sheet_url = st.text_input("Paste the Google Sheet URL for 'Part 5 - Company data':")

    if sheet_url:
        try:
            # create the CSV url
            csv_url = convert_to_csv_url(sheet_url)

            # Load and display csv data from url
            df = pd.read_csv(csv_url)
            st.write("Uploaded Dataset:")
            st.dataframe(df)

            # Identify the country in the new data and use it for filtering the remote database
            country = df['Country'].iloc[0]
            unique_companies = load_remote_dataset(country)

            # Preprocess both new and remote datasets
            df = preprocess_dataset(df)
            unique_companies['company_name'] = unique_companies['company_name'].apply(preprocess_text)

            # SECTION 2: Exact matches
            st.header("Matches Found")
            company_matches = pd.merge(df, unique_companies, left_on='Company', right_on='company_name', how='inner')

            st.subheader("Company Matches")
            st.dataframe(company_matches[['Company', 'eiti_id_company']])

            # SECTION 3: Unmatched with potential matches
            st.header("Unmatched Values with Potential Matches")
            unmatched_companies = df[~df['Company'].isin(company_matches['Company'])]

            unmatched_companies = unmatched_companies.drop_duplicates(subset=['Company'])
            unmatched_companies['Potential_Match'] = get_potential_matches(unmatched_companies['Company'], unique_companies['company_name'])
            unmatched_companies['EITI ID'] = ''

            display_unmatched(unmatched_companies, unique_companies, 'Company', 'company_name')

            # SECTION 4: Validate matching
            st.header("Validate Matching")
            if st.button("I am done matching"):
                df = validate_matching(df, company_matches, unmatched_companies)

                st.write("Matching complete. Download the updated dataset:")
                st.dataframe(df)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", data=csv, file_name='updated_dataset.csv', mime='text/csv')

        except Exception as e:
            st.error(f"Error loading data from URL: {e}")


# Run the app
if __name__ == "__page__":
    page()
