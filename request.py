#pylint: disable-all
import hashlib
import os
import re
import time
import urllib.parse, urllib.request
from bs4 import BeautifulSoup
from lxml import etree

ROOTS_FILE = "roots.xml"
CACHE_DIR = "cache"
OUTPUT_DIR = "output"
REQUEST_DELAY = 3
MAX_LEVEL = 2

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

def save_cache_file(filename, text, encoding):
    """Save a file to the cache directory."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    path = os.path.join(".", CACHE_DIR)
    path = os.path.join(path, filename)
    with open(path, mode="wt", encoding=encoding) as f:
        f.write(text)

def load_cached_file(url):
    """Get the BeautifulSoup object from the cache, or return None."""
    # Make sure the cache directory exists
    if os.path.exists(CACHE_DIR):
        # Get the URL hash 
        url_hash = get_unique_filename(url)
        # Loop through the files in the cache
        for fn in os.listdir(CACHE_DIR):
            # If there's a maching file
            if fn == url_hash:
                path = os.path.join(".", CACHE_DIR)
                path = os.path.join(path, fn)
                with open(path, mode="rt", encoding="utf-8") as f:
                    try:
                        html = f.read()
                        if len(html.strip()) > 0:
                            soup = BeautifulSoup(html, "lxml")
                            return soup
                        else:
                            raise ValueError("The cached file is empty:\n  " + url)
                    except IOError:
                        print("IOError when reading cached resource:\n  " + url)
                    except UnicodeDecodeError:
                        print("UnicodeDecodeError when reading cached resource:\n  " + url)
                    except ValueError as error:
                        print(str(error))
                    
    return None

def get_soup(url):
    """Get BeautifulSoup object from cache or web."""
    cached = False
    soup = load_cached_file(url)
    if soup:
        cached = True
    else:
        # If no cached soup was found, download the page
        with urllib.request.urlopen(url) as response:
            html = response.read()
            soup = BeautifulSoup(html, "lxml")
            encoding = get_encoding(soup)
            filename = get_unique_filename(url)
            save_cache_file(filename, soup.prettify(), encoding)
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

def get_domain(url):
    """Extract a domain name from a URL."""
    domain = urllib.parse.urlparse(url)[1]
    # Remove port (e.g. ':80')
    if ":" in domain:
        domain = domain[:domain.index(":")]
    # Remove all but the last two parts (e.g. 'www.' in 'www.example.com')
    while domain.count(".") > 1:
        parts = domain.split(".")
        domain = ".".join(parts[1:])
    return domain

def save_recipe(url, soup):
    domain = get_domain(url)
    filename = domain + ".xml"
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    path = os.path.join(".", OUTPUT_DIR)
    path = os.path.join(path, filename)
    # Create domain-specific XML file if it's missing
    if not os.path.exists(path):
        root = etree.Element("recipes")
        document = etree.ElementTree(root)
        document.write(path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    # Get list of ingredients
    ingredients = soup.select("span[itemprop='ingredients']")
    if len(ingredients) > 0:
        # Append recipe to domain-specific XML file
        document = etree.parse(path)
        root = document.getroot()
        recipe = etree.SubElement(root, "recipe")
        recipe.set("source", url)
        for i in ingredients:
            ingredient = etree.SubElement(recipe, "ingredient")
            ingredient.text = i.string.strip()
        document.write(path, encoding="utf-8", xml_declaration=True, pretty_print=True)

def handle_url(url, level):
    level += 1
    if level <= MAX_LEVEL:
        soup, cached = get_soup(url)
        print(url, "cached=" + str(cached))
        if not cached:
            encoding = get_encoding(soup)
            filename = get_unique_filename(url)
            save_cache_file(filename, soup.prettify(), encoding)
        if is_recipe_page(soup):
            save_recipe(url, soup)
        else:
            links = soup.find_all(is_recipe_link)
            for tag in links:
                url = tag.get("href")
                if url:
                    time.sleep(REQUEST_DELAY)
                    handle_url(url, level)

document = etree.parse(ROOTS_FILE)
root = document.getroot()
for child in root:
    url = child.attrib.get("url")
    if url and len(url.strip()) > 0:
        handle_url(url, 0)
