#pylint: disable-all
import hashlib
import os
import re
import time
import urllib.parse, urllib.request
from bs4 import BeautifulSoup

CACHE_DIR = "cache"
ROOTS_FILE = "roots.txt"
REQUEST_DELAY = 3
MAX_LEVEL = 1

url = "https://pylint.readthedocs.io/en/latest/faq.html"

def get_unique_filename(text):
    """Get a unique alpha-numeric filename using the first few characters from a SHA1 hash of the input string."""
    m = hashlib.sha1()
    m.update(bytes(text, encoding="utf-8"))
    filename = m.hexdigest()[:6]
    return filename

def get_encoding(soup):
    """Get the HTML file encoding, using BeautifulSoup."""
    tags = soup.find_all("meta")
    for tag in tags:
        if tag.get("http-equiv") and tag.get("http-equiv").lower() == "content-type":
            if tag.get("content"):
                content = re.search("charset=([a-z0-9-]+)", tag.get("content"))
                if content:
                    return content[1]
        if tag.get("charset"):
            return tag.get("charset")

def save_file(filename, text, encoding):
    """Save a file to the cache directory."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    path = os.path.join(".", CACHE_DIR)
    path = os.path.join(path, filename)
    with open(path, mode="wt", encoding=encoding) as f:
        f.write(text)

def get_cached_soup(url):
    """Get the BeautifulSoup object from the cache, or return None."""
    # Make sure the cache directory exists
    if os.path.exists(CACHE_DIR):
        # Get the URL hash 
        url_hash = get_unique_filename(url)
        # Loop through the files in the cache
        for fn in os.listdir(CACHE_DIR):
            # If there's a maching file
            if fn == url_hash:
                path = os.path.join("./cache", fn)
                # Find a way to store and read the encoding
                with open(path, mode="rt", encoding="utf-8") as f:
                    html = f.read()
                    soup = BeautifulSoup(html, "lxml")
                return soup
    return None

def get_soup(url):
    """Get BeautifulSoup object from cache or web."""
    cached = False
    soup = get_cached_soup(url)
    if soup:
        cached = True
    else:
        # If no cached soup was found, download the page
        with urllib.request.urlopen(url) as response:
            html = response.read()
            soup = BeautifulSoup(html, "lxml")
    return soup, cached

def is_recipe_link(tag):
    """Return true if the input tag is an <a> link to a recipe."""
    # TODO: Move this to a site-specific reader class
    if tag.name == "a" and tag.parent.name == "h3":
        class_list = tag.parent.get("class")
        if class_list and "recipeTitleList" in class_list:
            return True
    return False

def is_recipe_page(soup):
    # TODO: Move this to a site-specific reader class
    recipe = soup.find("div", class_="leftSideRecipe")
    if recipe:
        return True
    else:
        return False

def handle_url(url, level=1):
    print(url + " -- level " + str(level))
    if level <= MAX_LEVEL:
        soup, cached = get_soup(url)
        print(len(soup), cached)
        if not cached:
            encoding = get_encoding(soup)
            filename = get_unique_filename(url)
            save_file(filename, soup.prettify(), encoding)
        if is_recipe_page(soup):
            links = soup.find_all(is_recipe_link)
            for tag in links:
                url = tag.get("href")
                if url:
                    time.sleep(REQUEST_DELAY)
                    handle_url(url, level)
            level += 1

with open(ROOTS_FILE, mode="rt", encoding="utf-8") as f:
    # Read roots file line by line
    for url in f:
        url = url.strip()
        if len(url) > 0:
            handle_url(url)
