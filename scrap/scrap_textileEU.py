import os
import sys
import time
import random
import shutil
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# User-agent list for randomization
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
]

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
EXPORT_CSV = f"textilEU_{timestamp}.csv"
BASE_URL = "https://textil.eu/en/products/?pg={}"


def get_chrome_driver(user_agent, profile_dir=None):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument('--log-level=3')
        options.add_argument('--disable-logging')
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
        return webdriver.Chrome(options=options)
    except Exception as e:
        print(f"🚫 Failed to initiate Chrome driver: {e}")
        sys.exit(1)


def collect_all_product_urls():
    print("Collecting all product URLs...")
    product_urls = set()
    page = 1

    while True:
        url = BASE_URL.format(page)
        user_agent = random.choice(USER_AGENTS)
        profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1, 10000)}")
        driver = get_chrome_driver(user_agent, profile_dir)
        wait = WebDriverWait(driver, 15)

        try:
            print(f"Scraping URL: {url}")
            driver.get(url)
            time.sleep(random.uniform(2, 4))
            links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.item a.name")))
            page_urls = {link.get_attribute("href") for link in links if link.get_attribute("href")}

            if not page_urls or page_urls.issubset(product_urls):
                print(f"✅ Scraping complete. Total unique products: {len(product_urls)}")
                break

            product_urls.update(page_urls)
            print(f"  Page {page}: {len(page_urls)} new products found. Total: {len(product_urls)}")
            page += 1
            time.sleep(random.uniform(10, 20))

        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break

        finally:
            driver.quit()
            try:
                shutil.rmtree(profile_dir)
            except Exception as e:
                print(f"⚠️ Could not remove profile dir {profile_dir}: {e}")

    return list(product_urls)


def scrape_product(url, max_retries=3):
    for attempt in range(max_retries):
        user_agent = random.choice(USER_AGENTS)
        profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1, 10000)}")
        driver = get_chrome_driver(user_agent, profile_dir)
        wait = WebDriverWait(driver, 20)

        try:
            driver.get(url)
            time.sleep(random.uniform(5, 10))

            title = driver.find_element(By.CSS_SELECTOR, 'h1.hassubtitle').text.strip()
            description_elem = driver.find_element(By.CSS_SELECTOR, 'div#z1')
            description = description_elem.text.strip()

            details = {}
            tables = driver.find_elements(By.CSS_SELECTOR, 'table.table-detail, table.table')
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, 'tr')
                for row in rows:
                    try:
                        key = row.find_element(By.TAG_NAME, 'th').text.strip().replace(':', '')
                        val_element = row.find_element(By.TAG_NAME, 'td')
                        links = val_element.find_elements(By.TAG_NAME, 'a')
                        if links:
                            val = ', '.join(link.text.strip() for link in links)
                        else:
                            val = val_element.text.strip()
                        details[key] = val
                    except:
                        continue

            specs_summary = '; '.join(f"{k}: {v}" for k, v in details.items())

            return {
                "Product Title": title,
                "URL": url,
                "Description": description,
                "Specs Summary": specs_summary,
                "Details": details
            }

        except Exception as e:
            print(f"❌ Error scraping {url} (attempt {attempt+1}): {e}")
            time.sleep(random.uniform(10, 30))

        finally:
            driver.quit()
            try:
                shutil.rmtree(profile_dir)
            except Exception as e:
                print(f"⚠️ Could not remove profile dir {profile_dir}: {e}")

    return {
        "Product Title": "N/A",
        "URL": url,
        "Description": "N/A",
        "Specs Summary": "N/A",
        "Details": {}
    }


if __name__ == "__main__":
    all_urls = collect_all_product_urls()
    print(f"Total products found: {len(all_urls)}")

    if os.path.exists(EXPORT_CSV):
        partial_df = pd.read_csv(EXPORT_CSV)
        scraped_urls = set(partial_df['URL'])
        data = partial_df.to_dict('records')
        print(f"Resuming: {len(scraped_urls)} products already scraped.")
    else:
        scraped_urls = set()
        data = []

    urls_to_scrape = [url for url in all_urls if url not in scraped_urls]

    for idx, url in enumerate(urls_to_scrape, start=len(scraped_urls) + 1):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{Fore.CYAN}📄 [{timestamp}] Scraping item {idx} of {len(all_urls)}:{Style.RESET_ALL}\n{Fore.GREEN}🔗 {url}{Style.RESET_ALL}")
        data.append(scrape_product(url))
        time.sleep(random.uniform(10, 30))

        if idx % 20 == 0:
            pd.DataFrame(data).to_csv(EXPORT_CSV, index=False)

    if data:
        df = pd.DataFrame(data)
        print("\n🧵 Sample Data Preview:")
        print(df.head())
        df.to_csv(EXPORT_CSV, index=False)
        print(f"✅ Final data saved to {EXPORT_CSV}")
    else:
        print("No data scraped.")
