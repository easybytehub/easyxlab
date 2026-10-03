"""Inside Airbnb snapshots used by S11 (the last scrape before and the first after 20 May 2026).
Dates are Inside Airbnb's publishDate, which is also the folder name on data.insideairbnb.com."""
ROOT = "https://data.insideairbnb.com/"
SNAPSHOTS = [
    # area key, Inside Airbnb path, before (March 2026), after (June 2026)
    ("barcelona", "spain/catalonia/barcelona", "2026-03-21", "2026-06-24"),
    ("girona", "spain/catalonia/girona", "2026-03-31", "2026-06-30"),
    ("valencia", "spain/vc/valencia", "2026-03-28", "2026-06-26"),
    ("malaga", "spain/andalucía/malaga", "2026-03-31", "2026-06-30"),
    ("sevilla", "spain/andalucía/sevilla", "2026-03-31", "2026-06-30"),
    ("madrid", "spain/comunidad-de-madrid/madrid", "2026-03-24", "2026-06-20"),
    ("nyc", "united-states/ny/new-york-city", "2026-03-16", "2026-06-14"),
]
REGION = {"barcelona": "catalonia", "girona": "catalonia", "valencia": "valencia",
          "malaga": "andalucia", "sevilla": "andalucia", "madrid": "madrid", "nyc": "nyc"}


def url(path, date):
    from urllib.parse import quote
    return ROOT + quote(f"{path}/{date}/data/listings.csv.gz")


def raw_path(area, date):
    return f"data/raw/insideairbnb/{area}_{date}_listings.csv.gz"
