import random
import time
import pandas as pd
import os
import shutil
import threading
from urllib.parse import urlparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
]

EXPORT_FILENAME = "fabricdepot_full_export.csv"
MAX_WORKERS = 1
csv_lock = threading.Lock()

def get_chrome_driver(user_agent, profile_dir=None):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={user_agent}")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2
    }
    options.add_experimental_option("prefs", prefs)
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
    return webdriver.Chrome(options=options)

def collect_all_product_urls():
    print("🔍 Collecting all product URLs from all pages...")
    base_url = "https://fabricdepot.com/collections/apparel-fabric?page={}&sort=created-descending&size=48"
    collected_urls = set()
    page = 1
    user_agent = random.choice(USER_AGENTS)
    profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1, 10000)}")
    driver = get_chrome_driver(user_agent, profile_dir)
    wait = WebDriverWait(driver, 15)

    try:
        while True:
            url = base_url.format(page)
            print(f"🌐 Scraping page {page}: {url}")
            driver.get(url)
            time.sleep(random.uniform(2, 4))

            links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.mz-grid.collection-listing.product-list a.product-link")))
            if not links:
                print("❌ No products found. Stopping.")
                break

            new_links = {
                link.get_attribute("href") if link.get_attribute("href").startswith("http")
                else "https://fabricdepot.com" + link.get_attribute("href")
                for link in links if link.get_attribute("href")
            }

            if not new_links or new_links.issubset(collected_urls):
                print("✅ No new links found. Reached end of catalog.")
                break

            collected_urls.update(new_links)
            print(f"✅ Found {len(new_links)} new product URLs (total: {len(collected_urls)})")
            page += 1

    except Exception as e:
        print(f"❌ Error while scraping product pages: {e}")
    finally:
        driver.quit()
        try:
            shutil.rmtree(profile_dir)
        except:
            pass

    return list(collected_urls)

def parse_fabric_description(description):
    details = {}
    lines = description.splitlines()
    for line in lines:
        line = line.strip("- ").strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            details[key.strip()] = value.strip()
        else:
            details["Marketing Description"] = line.strip()
    return details

def scrape_and_save(url):
    record = scrape_product(url)
    if record["Product Title"] != "N/A":
        with csv_lock:
            df = pd.DataFrame([record])
            df.to_csv(EXPORT_FILENAME, mode='a', header=not os.path.exists(EXPORT_FILENAME), index=False)
            print(f"✅ Appended to {EXPORT_FILENAME}: {url}")
    else:
        print(f"⚠️ Skipped due to missing title: {url}")

def scrape_product(url, max_retries=3):
    for attempt in range(max_retries):
        user_agent = random.choice(USER_AGENTS)
        profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1,10000)}")
        driver = get_chrome_driver(user_agent, profile_dir)
        wait = WebDriverWait(driver, 20)
        result = {}
        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(random.uniform(3, 6))

            try:
                title = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.title"))).text.strip()
            except:
                print("⚠️ Title not found.")
                title = "N/A"

            try:
                desc_block = driver.find_element(By.CSS_SELECTOR, "div.product-description.rte.cf")
                raw_description = desc_block.get_attribute("innerText").strip()
                description = raw_description
                parsed_details = parse_fabric_description(raw_description)
            except:
                print("⚠️ Description not found.")
                description = "N/A"
                parsed_details = {}

            try:
                thumbnails = driver.find_elements(By.CSS_SELECTOR, "a.thumbnail.thumbnail--media-image")
                image_urls = []
                for thumb in thumbnails:
                    try:
                        img = thumb.find_element(By.CSS_SELECTOR, "img.rimage__image")
                        srcset = img.get_attribute("data-srcset")
                        if srcset:
                            pairs = [pair.strip() for pair in srcset.split(",")]
                            for pair in pairs:
                                url_part, size = pair.rsplit(" ", 1)
                                if size.strip() == "2048w":
                                    if url_part.startswith("//"):
                                        url_part = "https:" + url_part
                                    image_urls.append(url_part)
                    except Exception as e:
                        print(f"⚠️ Could not parse image in thumbnail: {e}")
            except Exception as e:
                print("⚠️ Product thumbnails not found.")
                image_urls = []

            result = {
                "Product Title": title,
                "URL": url,
                "Description": description,
                "Image URLs": "; ".join(image_urls)
            }
            result.update(parsed_details)
            return result
        except Exception as e:
            print(f"❌ Error scraping {url} (attempt {attempt+1}): {e}")
            time.sleep(random.uniform(10, 30))
        finally:
            driver.quit()
            try:
                shutil.rmtree(profile_dir)
            except:
                pass

    print(f"❌ Failed to scrape {url} after {max_retries} attempts. Skipping.")
    return {
        "Product Title": "N/A",
        "URL": url,
        "Description": "N/A",
        "Image URLs": "N/A"
    }

if __name__ == "__main__":
    start_time = datetime.now()
    print(f"🚀 Scraping started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_urls = collect_all_product_urls()
    print(f"\n📦 Total products found across all pages: {len(all_urls)}")

    scraped_urls = set()
    if os.path.exists(EXPORT_FILENAME):
        try:
            df_existing = pd.read_csv(EXPORT_FILENAME)
            scraped_urls.update(df_existing['URL'].dropna().tolist())
            print(f"🔁 Resuming. {len(scraped_urls)} products already scraped.")
        except Exception as e:
            print(f"⚠️ Failed to read existing export file: {e}")

    urls_to_scrape = [url for url in all_urls if url not in scraped_urls]
    total_to_scrape = len(urls_to_scrape)
    print(f"🚧 Starting scrape of {total_to_scrape} remaining products with {MAX_WORKERS} threads...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_and_save, url): url for url in urls_to_scrape}
        for i, future in enumerate(as_completed(futures), start=1):
            future.result()
            elapsed = (datetime.now() - start_time).total_seconds()
            eta = (elapsed / i) * (total_to_scrape - i) if i > 0 else 0
            print(f"🕐 Progress: {i}/{total_to_scrape} | ETA: {int(eta)} seconds")

    end_time = datetime.now()
    print(f"✅ Scraping completed at {end_time.strftime('%Y-%m-%d %H:%M:%S')} | Total time: {(end_time - start_time)}")
