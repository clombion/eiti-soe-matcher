import streamlit as st
import pandas as pd
import uuid
from fuzzywuzzy import process
import unidecode
from urllib.request import Request, urlopen

# Function to convert the Google Sheets into a CSV link
def convert_to_csv_url(view_url):
    file_id = view_url.split('/')[5]
    gid = view_url.split('gid=')[-1]
    return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid={gid}"

# Function to load the remote dataset and filter by country
@st.cache_data
def load_remote_dataset(country):
    url = 'https://soe-database.eiti.org/eiti_database/projects.csv?_size=max'
    req = Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0')
    content = urlopen(req)
    remote_df = pd.read_csv(content)
    filtered_df = remote_df[remote_df['country'].str.upper() == country.upper()]
    unique_projects = filtered_df.drop_duplicates(subset=['eiti_id_project'])
    return unique_projects

# Function to generate UUID4
def generate_uuid():
    return str(uuid.uuid4())

# Function to preprocess text
def preprocess_text(text):
    if isinstance(text, str):  # Check if the input is a string
        return unidecode.unidecode(text).upper()
    else:
        return text  # Return as is if not a string (e.g., NaN)

# Function to preprocess the new data
def preprocess_dataset(df, column_name):
    df[column_name] = df[column_name].apply(preprocess_text)
    return df

# Function to get potential matches using fuzzy matching, considering secondary criteria
def get_potential_matches(unmatched_series, remote_df, primary_column, secondary_column=None):
    def get_match(x):
        # Primary match (project name)
        primary_match = process.extractOne(x[primary_column], remote_df[primary_column])
        if primary_match[1] >= 90:  # High confidence primary match
            return primary_match[0]

        # Secondary match (legal agreement), only if primary match is weak
        if secondary_column and isinstance(x[secondary_column], str) and x[secondary_column].strip(): #check if string and not emtpy
            secondary_matches = process.extract(x[secondary_column], remote_df[secondary_column].astype(str))
            for match_str, score in secondary_matches:
                if score >= 90:
                    # Find corresponding project name
                    matched_row = remote_df[remote_df[secondary_column].astype(str) == match_str]
                    if not matched_row.empty:
                        return matched_row[primary_column].iloc[0]
        return "No potential match"

    potential_matches = unmatched_series.apply(get_match, axis=1)
    return potential_matches



# Function to display unmatched entities with potential matches
def display_unmatched(unmatched_df, remote_df, entity_type, primary_column, secondary_column):
    st.subheader(f"Unmatched {entity_type.capitalize()}s")
    for index, row in unmatched_df.iterrows():
      options = ['No potential match'] + remote_df[primary_column].tolist()
      selected_match = st.selectbox(
          f"Potential Match for {row[primary_column]} (Ref: {row.get(secondary_column, 'N/A')})",
          options=options,
          key=f"{entity_type}_match_{index}"
      )
      unmatched_df.at[index, 'Potential_Match'] = selected_match

      if selected_match != 'No potential match':
          unmatched_df.at[index, 'EITI ID'] = remote_df[remote_df[primary_column] == selected_match]['eiti_id_project'].values[0]
    st.dataframe(unmatched_df)

# Function to validate and finalize matching
def validate_matching(df, matches, unmatched, primary_column, id_column):
    unmatched['EITI ID'] = unmatched['EITI ID'].replace('', pd.NA).fillna(generate_uuid())
    unmatched_mapping = unmatched.drop_duplicates(subset=[primary_column]).set_index(primary_column)['EITI ID']

    df = pd.merge(df, matches[[primary_column, id_column]], on=primary_column, how='left')
    df[id_column] = df[id_column].fillna(df[primary_column].map(unmatched_mapping))
    return df


# --- Main Streamlit App ---
def page():
    st.header("Project Entities")

    sheet_url = st.text_input("Paste your Google Sheet URL for Projects:")

    if sheet_url:
        try:
            csv_url = convert_to_csv_url(sheet_url)
            df = pd.read_csv(csv_url)
            st.write("Uploaded Dataset:")
            st.dataframe(df)

            country = df['Country'].iloc[0]
            unique_projects = load_remote_dataset(country)
            # Preprocess
            df = preprocess_dataset(df, 'Full project name')
            df = preprocess_dataset(df, "Legal agreement reference number(s): contract, licence, lease, concession, …")  # Preprocess secondary column
            unique_projects = preprocess_dataset(unique_projects, 'project_name')
            unique_projects = preprocess_dataset(unique_projects, "Legal agreement reference number(s): contract, licence, lease, concession, …")  # Preprocess secondary

            # Exact Matches
            st.header("Matches Found")
            project_matches = pd.merge(df, unique_projects, left_on='Full project name', right_on='project_name', how='inner')
            st.subheader("Project Matches")
            st.dataframe(project_matches[['Full project name', 'eiti_id_project']])

            # Unmatched
            st.header("Unmatched Values with Potential Matches")
            unmatched_projects = df[~df['Full project name'].isin(project_matches['Full project name'])]
            unmatched_projects = unmatched_projects.drop_duplicates(subset=['Full project name'])

            if not unmatched_projects.empty:
                unmatched_projects['Potential_Match'] = get_potential_matches(
                    unmatched_projects, unique_projects, 'Full project name', "Legal agreement reference number(s): contract, licence, lease, concession, …"
                )
                unmatched_projects['EITI ID'] = ''
                display_unmatched(unmatched_projects, unique_projects, 'Project', 'project_name', "Legal agreement reference number(s): contract, licence, lease, concession, …")
            else:
                st.info("All projects matched perfectly!")

            # Validate
            st.header("Validate Matching")
            if st.button("I am done matching"):
                df = validate_matching(df, project_matches, unmatched_projects, 'Full project name', 'eiti_id_project')

                # Select and rename columns for output
                output_df = df.rename(columns={
                  'Full project name': 'project_name',
                  'Legal agreement reference number(s): contract, licence, lease, concession, …': 'Legal agreement reference number(s): contract, licence, lease, concession, …',
                  'ISO Code': 'iso_alpha3_code',
                  'EITI ID' : 'eiti_id_project'
                })

                # Ensure output_df has all the required columns, filling missing ones with appropriate defaults
                required_cols = ['rowid', 'project_name', 'eiti_id_project', 'Legal agreement reference number(s): contract, licence, lease, concession, …',
                                 'affiliated_companies', 'commodities', 'status', 'production_volume', 'unit', 'production_value',
                                 'currency', 'country', 'iso_alpha3_code', 'eiti_id_declaration', 'year', 'start_date', 'end_date']
                for col in required_cols:
                    if col not in output_df.columns:
                        # Use a dictionary to specify default values for different columns
                        default_values = {
                            'rowid': None,  # or generate a sequence if needed
                            'affiliated_companies': 'n/a',
                            'commodities': 'n/a',
                            'status': 'n/a',
                            'production_volume': '',
                            'unit': 'n/a',
                            'production_value': '',
                            'currency': 'n/a',
                            'eiti_id_declaration': '',  # Consider generating a default UUID
                            'year': '', # or extract from Google Sheet if possible
                            'start_date' : '',
                            'end_date' : '',
                            'eiti_id_project': ''

                        }
                        output_df[col] = default_values.get(col, None)  # Fill missing columns

                output_df = output_df[required_cols]


                st.write("Matching complete. Download the updated dataset:")
                st.dataframe(output_df)
                csv = output_df.to_csv(index=False, encoding='utf-8')
                st.download_button("Download CSV", data=csv, file_name='updated_projects.csv', mime='text/csv')


        except Exception as e:
            st.error(f"Error: {e}")

# Entry point for Streamlit multi-page app
if __name__ == "__page__":
    page()