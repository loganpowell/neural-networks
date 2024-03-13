import requests
import re
from fns.soup_fns import html2md_clean


def page_scraper(url):
    """
    scrapes the text from a web page
    """
    url_rx = re.compile(r"https?://[^\s]+")

    url = url_rx.search(url).group(0)
    
    print(f"page_scraper: Scraping: {url}")
    # remove extra wrapping quotes from string
    url = url.strip('\"')

    response = requests.get(url, timeout=20)
    if not response.ok:
        raise requests.exceptions.HTTPError(f"HTTP error {response.status_code}")
    md = html2md_clean(response.text)
    return md