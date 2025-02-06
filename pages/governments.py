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
    url = 'https://soe-database.eiti.org/eiti_database/agencies.csv?_size=max'
    req = Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0')
    content = urlopen(req)

    remote_df = pd.read_csv(content)
    filtered_df = remote_df[remote_df['country'].str.upper() == country.upper()]
    unique_governments = filtered_df.drop_duplicates(subset=['eiti_id_government'])
    return unique_governments


# Function to generate UUID4
def generate_uuid():
    return str(uuid.uuid4())


# Function to preprocess text (convert to uppercase and remove diacritics)
def preprocess_text(text):
    return unidecode.unidecode(text).upper()


# Function to preprocess the new data
def preprocess_dataset(df):
    df['Government entity'] = df['Government entity'].apply(preprocess_text)
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
            unmatched_df.at[index, 'EITI ID'] = remote_df[remote_df[remote_column] == unmatched_df.at[index, 'Potential_Match']]['eiti_id_government'].values[0]
    st.dataframe(unmatched_df)


# Function to validate and finalize matching
def validate_matching(df, gov_matches, unmatched_governments):
    # Skip merging unmatched if no unmatched entries exist
    if unmatched_governments.empty:
        return pd.merge(df, gov_matches[['Government entity', 'eiti_id_government']], on='Government entity', how='left')

    # Merge matched entities and fill unmatched IDs
    df = pd.merge(df, gov_matches[['Government entity', 'eiti_id_government']], on='Government entity', how='left')
    df['eiti_id_government'] = df['eiti_id_government'].combine_first(
        unmatched_governments.set_index('Government entity')['EITI ID']
    )
    return df

# Main function to run the Streamlit app
def page():
    st.header("Government entities")

    # SECTION 1: Input Google Sheet URL
    sheet_url = st.text_input("Paste your Google Sheet URL for 'Part 4 - Government revenues:")

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
            unique_governments = load_remote_dataset(country)

            # Preprocess both new and remote datasets
            df = preprocess_dataset(df)
            unique_governments['government_entity'] = unique_governments['government_entity'].apply(preprocess_text)

            # SECTION 2: Exact matches
            st.header("Matches Found")
            gov_matches = pd.merge(df, unique_governments, left_on='Government entity', right_on='government_entity', how='inner')
            st.subheader("Government Entity Matches")
            st.dataframe(gov_matches[['Government entity', 'eiti_id_government']])

            # SECTION 3: Unmatched with potential matches
            st.header("Unmatched Values with Potential Matches")
            unmatched_governments = df[~df['Government entity'].isin(gov_matches['Government entity'])]

            # Handle unmatched entries if they exist
            if unmatched_governments.empty:
                st.info("No unmatched entities. All entries have been matched perfectly!")
            else:
                unmatched_governments['Potential_Match'] = get_potential_matches(
                    unmatched_governments['Government entity'],
                    unique_governments['government_entity']
                )
                unmatched_governments['EITI ID'] = ''
                display_unmatched(unmatched_governments, unique_governments, 'Government entity', 'government_entity')

            # SECTION 4: Validate matching
            st.header("Validate Matching")
            if st.button("I am done matching"):
                if unmatched_governments.empty:
                    # Handle case where no unmatched entities exist
                    df = pd.merge(df, gov_matches[['Government entity', 'eiti_id_government']], on='Government entity', how='left')
                else:
                    unmatched_governments['EITI ID'] = unmatched_governments['EITI ID'].replace('', pd.NA).fillna(generate_uuid())
                    df = validate_matching(df, gov_matches, unmatched_governments)

                st.write("Matching complete. Download the updated dataset:")
                st.dataframe(df)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", data=csv, file_name='updated_dataset.csv', mime='text/csv')

        except Exception as e:
            st.error(f"Error loading data from URL: {e}")

# Run the app
if __name__ == "__page__":
    page()
