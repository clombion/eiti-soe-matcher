import streamlit as st

homepage = st.Page("./pages/homepage.py", title="Instructions")
companies_page = st.Page("./pages/companies.py", title="Companies", icon=":material/source_environment:")
governments_page = st.Page("./pages/governments.py", title="Governments", icon=":material/account_balance:")

pg = st.navigation([homepage, companies_page, governments_page])
st.set_page_config(page_title="EITI Data Matcher", page_icon=":material/edit:")

pg.run()