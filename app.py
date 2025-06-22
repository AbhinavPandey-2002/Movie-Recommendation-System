import streamlit as st
import pickle
import pandas as pd
import numpy as np
import requests
import os


OMDB_API_KEY = "e160367f"


CACHE_FILE = "poster_cache.pkl"


if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "rb") as f:
        poster_cache = pickle.load(f)
else:
    poster_cache = {}


similarity = pickle.load(open("similarity.pkl", "rb"))
movies_data = pickle.load(open("movies.pkl", "rb"))


if "poster_path" in movies_data.columns:
    local_posters = {}
    for _, row in movies_data.iterrows():
        title = row["title"]
        p = row["poster_path"]
        if pd.notna(p) and isinstance(p, str) and p.strip():
            
            local_posters[title] = f"https://image.tmdb.org/t/p/w500{p}"
        else:
            local_posters[title] = None
else:
    local_posters = {}



def url_exists(url: str) -> bool:
    
    try:
        
        r = requests.head(url, timeout=3)
        if r.status_code == 200:
            return True
        
        if r.status_code in (405, 403):
            r2 = requests.get(url, stream=True, timeout=5)
            return r2.status_code == 200
        return False
    except:
        return False



def fetch_poster(title: str) -> str | None:
    """
    1) If TMDb local poster_path exists and is valid (HTTP 200), return it.
    2) Else if cached (title in poster_cache), return that cached URL or None.
    3) Otherwise, query OMDb, verify it, cache result (or None), and return.
    """

    
    if title in local_posters and local_posters[title]:
        candidate = local_posters[title]
        if url_exists(candidate):
            return candidate
        
        local_posters[title] = None

    
    if title in poster_cache:
        return poster_cache[title]

    
    try:
        omdb_url = (
            f"http://www.omdbapi.com/?t={requests.utils.quote(title)}"
            f"&apikey={OMDB_API_KEY}"
        )
        res = requests.get(omdb_url, timeout=5)
        data = res.json()
        if data.get("Response") == "True" and data.get("Poster") not in ["N/A", None]:
            candidate = data["Poster"]
            if url_exists(candidate):
                poster_url = candidate
            else:
                poster_url = None
        else:
            poster_url = None
    except:
        poster_url = None

    
    poster_cache[title] = poster_url
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(poster_cache, f)

    return poster_url



def recommend(movie_title: str) -> pd.DataFrame:
    """
    Return a DataFrame of the top-10 most similar movies (including the input).
    We’ll remove the input movie itself downstream.
    """
    idx = movies_data[movies_data["title"] == movie_title].index[0]
    sims = similarity[idx]
    
    top10_idxs = np.argsort(sims)[::-1][:10]
    df_sim = movies_data.iloc[top10_idxs].copy()
    df_sim["similarity"] = sims[top10_idxs]
    return df_sim.sort_values(by="similarity", ascending=False)



st.title("🎬 Movie Recommender")

selected_movie = st.selectbox("Select a movie:", movies_data["title"].values)

if st.button("Recommend"):
    recs = recommend(selected_movie)
    recs = recs[recs["title"] != selected_movie]  

    shown = 0
    cols = st.columns(5)

    for _, row in recs.iterrows():
        if shown >= 5:
            break

        title = row["title"]
        poster_url = fetch_poster(title)

        
        if poster_url is None:
            continue

        with cols[shown % 5]:
            st.image(poster_url, use_column_width=True)
            st.caption(title)

        shown += 1

    if shown == 0:
        st.warning("No valid posters found among the top 9 similar movies.")
