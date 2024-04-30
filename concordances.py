import os
import streamlit as st

import sqlite3
import pandas as pd
from dhlab.api.dhlab_api import totals
from collections import Counter
import socket
import dhlab as dh
import requests
from io import BytesIO
import openpyxl

st.set_page_config(page_title="Konkordanser", page_icon=None, layout="wide", initial_sidebar_state="auto", menu_items=None)
st.title("Konkordanser")
st.write("Lagre konkordanser med årstall")

def to_excel(df):
    """Make an excel object out of a dataframe as an IO-object"""
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.close()
    worksheet = writer.sheets['Sheet1']
    processed_data = output.getvalue()
    return processed_data



@st.cache_data()
def concordance(
        dhlabids = None, words = None, window = 25, limit = 100
):
    """Get a list of concordances from the National Library's database.

    Call the API :py:obj:`~dhlab.constants.BASE_URL` endpoint
    `/conc <https://api.nb.no/dhlab/#/default/post_conc>`_.

    :param list urns: uniform resource names, for example:
        ``["URN:NBN:no-nb_digibok_2008051404065", "URN:NBN:no-nb_digibok_2010092120011"]``
    :param str words: Word(s) to search for.
        Can be an SQLite fulltext query, an fts5 string search expression.
    :param int window: number of tokens on either side to show in the collocations, between 1-25.
    :param int limit: max. number of concordances per document. Maximum value is 1000.
    :return: a table of concordances
    """
    if words is None:
        return {}  # exit condition
    else:
        #st.write("antall urner:", len(urns))
        params = {"dhlabids": dhlabids, "query": words, "window": window, "limit": limit}
        r = requests.post(dh.constants.BASE_URL + "/conc", json=params)
        if r.status_code == 200:
            res = r.json()
        else:
            res = []
    return pd.DataFrame(res)

def show_concs(corpus, concs, search, number):
    for row in concs.sample(min(len(concs),number)).iterrows():
        urn = row[1]["urn"]
        metadata = corpus[corpus["urn"] == urn][['title', 'authors', 'year', 'timestamp']]
        metadata = metadata.iloc[0]
        metadata.year = metadata.year.astype(int)
        if 'digavis' in urn:
            timestamp = metadata["timestamp"]
        else:
            timestamp = metadata["year"]

        if metadata["authors"] is None:
            metadata["authors"] = ""
        if metadata["title"] is None:
            metadata["title"] = ""

        url = f"https://nb.no/items/{urn}?searchText={search}"
        link = "<a href='%s' target='_blank'>%s – %s – %s</a>" % (url, metadata["title"], metadata["authors"], timestamp)

        conc_markdown = row[1]["conc"].replace('<b>', '**')
        conc_markdown = conc_markdown.replace('</b>', '**')
        html = "%s %s" % (link, conc_markdown)
        st.markdown(html, unsafe_allow_html=True)

corpusfile = st.file_uploader("Last opp et korpus", help="Dra en fil over hit, fra et nedlastningsikon, eller velg fra en mappe")
if corpusfile is not None:
    corpus_defined = True
    dataframe = pd.read_excel(corpusfile)
    corpus = dh.Corpus(doctype='digibok',limit=0)
    corpus.extend_from_identifiers(list(dataframe.urn))
    corpus = corpus.frame

col1, col2, col3, col4 = st.columns(4)
with col1:
    konk_ord = st.text_input("konkordans for", st.session_state.get('conc_word', ''), key='conc_word')
with col2:
    antall = st.number_input("maks antall konkordanser", min_value = 1, max_value = 5000, value = st.session_state.get('conc_numbers', 1000), key='conc_numbers')
with col3:
    kontekst = st.number_input('konkordansevindu', min_value = 1, max_value = 100, value = 25, key = 'conc_window')
with col4:
    limit = st.number_input("antall konkordanser som vises", min_value=5, max_value = 200, value=50)

concs = concordance(list(corpus.dhlabid.values), words=konk_ord, limit=antall, window=kontekst)

st.write(f"Fant {len(concs)} konkordanser viser {min(len(concs), limit)} av dem")

st.write("# Konkordanser med årstall og lenke - klikk på lenken for å se på teksten")
show_concs(corpus, concs, konk_ord,limit)

excel_fil = to_excel(concs.merge(corpus, left_on='urn', right_on='urn')[["urn","year","conc"]])

filnavn = st.text_input("Filnavn for excelfil", "konkordanser.xlsx")
st.download_button(
    label = f"Last ned alle {len(concs)} konkordansene ",
    data = excel_fil,
    file_name = filnavn,
    mime='application/msexcel',
)
