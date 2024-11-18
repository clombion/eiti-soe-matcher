import streamlit as st

st.title("EITI Data Matcher")

st.write("Use this app to match new summary sata with existing EITI IDs in the SOE database. Each finalized matching outputs a CSV file which can then be uploaded to the SOE database.")

st.subheader("Instructions")
st.markdown('''Use the sidebar to select the entities that you want to match. To add the IDs to a new summary data file:
1. normalise the data using a copy of the [standardized template ](https://docs.google.com/spreadsheets/d/1XoERAe9AULpxd8F6GrkMrfTN8boJ0Qv1FGRaeRu2oRg/edit?gid=0#gid=0)
2. set the sharing status of the spreadsheet to 'Anyone with the link'
3. Switch to the tab corresponding to the entity to be matched and copy and the url
4. Paste the url in the entry field in the data matching app. A table will be generatee to help you confirm that you have selected the correct url.
5. Finalise the matching process, and a CSV will be downloaded''')

