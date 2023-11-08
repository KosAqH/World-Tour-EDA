import requests
from bs4 import BeautifulSoup
import pandas as pd
from geopy.geocoders import Nominatim

captions1 = [
    "Top 20 highest-grossing tours of all time",
    "Top 10 highest-grossing tours of the 1980s",
    "Top 10 highest-grossing tours of the 1990s",
    "Top 10 highest-grossing tours of the 2000s",
    "Top 10 highest-grossing tours of the 2010s",
    "Top 10 highest-grossing tours of the 2020s"
]

captions2 = [
    "Tours attended by 5 million people or more",
    "Tours attended by 3.5 to 4.9 million people"
]

URL_TOUR1 = "https://en.wikipedia.org/wiki/List_of_highest-grossing_concert_tours"
URL_TOUR2 = "https://en.wikipedia.org/wiki/List_of_most-attended_concert_tours"
WIKI_BASE_URL = "https://en.wikipedia.org/"

def create_tour_list() -> pd.DataFrame:
    tours1 = get_tours(captions1, URL_TOUR1)
    tours2 = get_tours(captions2, URL_TOUR2)

    tours1 = prepare_data(tours1)
    tours2 = tours2[["Year(s)", "Tour title", "Tour link", "Artist", "Shows", "Tickets sold"]]

    df = combine_tours(tours1, tours2)

    return df

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={df.columns[3]: 'Adjusted gross (in 2022 dollars)',
                   df.columns[-1]: 'Adjusted gross (in 2022 dollar)',
                   df.columns[2]: 'Actual gross'})
    df.loc[df['Adjusted gross (in 2022 dollars)'].isna(), 'Adjusted gross (in 2022 dollars)'] = df['Adjusted gross (in 2022 dollar)']
    df = df[["Actual gross", "Adjusted gross (in 2022 dollars)", "Artist", "Tour title", "Tour link", "Year(s)", "Shows"]]
    return df

def get_tours(captions, url):
    df = pd.DataFrame()
    for caption in captions:
        df_tmp = pd.read_html(url, 
                          match=caption)[0]
        
        tour_links = pd.read_html(url, 
                  match=caption,
                  extract_links="all")[0][("Tour title", None)]
        
        tour_links = pd.DataFrame(tour_links.tolist(), columns=["Tour title", "Tour link"])
        df_tmp = df_tmp.merge(tour_links, on="Tour title")

        df = pd.concat([df, df_tmp]).drop_duplicates('Tour title').reset_index(drop=True)
    
    return df

def combine_tours(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([df1, df2])\
        .drop_duplicates('Tour link')\
        .reset_index(drop=True)
    return df

def create_show_list(df: pd.DataFrame) -> pd.DataFrame:
    df_shows = pd.DataFrame()
    df = df.drop(index=[50, 35]).reset_index()
    #index 50 - duplicated; 35 - wrong wiki page, no info about tour

    for _, row in df.iterrows():
        url = WIKI_BASE_URL + row["Tour link"]
        response = requests.get(url=url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for t in soup.body.findAll("table"):
            if "Cancelled shows" in str(t.find_previous_sibling()):
                t.clear()

        tables = pd.read_html(str(soup))
        df_show_tmp = pd.DataFrame()
        for t in tables:
            if "City" in t.columns and "Country" in t.columns:
                t.columns = t.columns.get_level_values(0)
                for i, _ in enumerate(t.columns):
                    if t.columns[i].startswith("Date"):
                        t = t.rename(columns={t.columns[i] : "Date"})
                df_show_tmp = pd.concat([df_show_tmp, t[["Country", "City", "Venue", "Date"]]])
        df_show_tmp = df_show_tmp.drop(df_show_tmp[df_show_tmp["Date"] == df_show_tmp["City"]].index)
        df_show_tmp["Artist"] = row["Artist"]
        df_show_tmp["Tour title"] = row["Tour title"]
        
        df_shows = pd.concat([df_shows, df_show_tmp])
    return df_shows

def get_geolocation(df: pd.DataFrame):
    cached_locations = {}
    geolocator = Nominatim(user_agent="my_user_agent")
    for index, _ in df.iterrows():
        venue = f"{df.iloc[index, 1]}, {df.iloc[index, 0]}"
        if venue in cached_locations:
            df.loc[index, "Latitude"] = cached_locations[venue][0]
            df.loc[index, "Longtitude"] = cached_locations[venue][1]
        else:
            location = geolocator.geocode(venue, timeout=10)
            df.loc[index, "Latitude"] = location.latitude
            df.loc[index, "Longtitude"] = location.longitude
            cached_locations[venue] = [location.latitude, location.longitude]
    return df

def fix_wrong_names(df: pd.DataFrame) -> pd.DataFrame:
    df.loc[df["Country"] == "West Germany", "Country"] = "Germany"
    df.loc[df["Country"] == "Ireland, Republic of", "Country"] = "Ireland"
    df.loc[df["Country"] == "Czechoslovakia", "Country"] = "Czech Republic"
    df.loc[df["Country"] == "Soviet Union", "Country"] = "Russia"
    df.loc[df["Country"] == "East Germany", "Country"] = "Germany"

    df.loc[df["Country"] == "Taiwan[21][22]", "Country"] = "Taiwan"

    df.loc[df["City"] == "Langraaf", "City"] = "Landgraaf"
    df.loc[df["City"] == "Mursfreesboro", "City"] = "Murfreesboro"
    df.loc[df["City"] == "East Berlin", "City"] = "Berlin"

    return df

if __name__ == "__main__":
    tours = create_tour_list()
    print("Created tour df.")
    shows = create_show_list(tours)
    print("Created shows list")
    shows = get_geolocation(shows)
    print("Add geolocation")
    shows.to_csv("prepared_data_2.csv", encoding="utf-8")