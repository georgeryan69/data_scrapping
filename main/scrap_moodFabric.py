import random
import time
import pandas as pd
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
]

def get_chrome_driver(user_agent, profile_dir=None):
    options = Options()
    options.add_argument("--headless")
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
    print("Collecting all product URLs...")
    product_urls = set()  # Use a set to ensure unique URLs
    page = 1
    while True:
        # Updated URL
        url = f"https://www.moodfabrics.com/fashion-fabrics?product_list_limit=120&p={page}"
        user_agent = random.choice(USER_AGENTS)
        profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1,10000)}")
        driver = get_chrome_driver(user_agent, profile_dir)
        wait = WebDriverWait(driver, 15)
        try:
            print(f"Scraping URL: {url}")
            driver.get(url)

            # Ensure the page is fully loaded
            state = driver.execute_script("return document.readyState")
            if state != "complete":
                print(f"⚠️ Page {page} not fully loaded. Retrying...")
                time.sleep(5)
                continue

            time.sleep(random.uniform(2, 4))
            links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.product-item-link")))
            page_urls = {link.get_attribute("href") for link in links if link.get_attribute("href")}

            if not page_urls or page_urls.issubset(product_urls):
                print(f"✅ Scraping complete. Total unique products: {len(product_urls)}")
                driver.quit()
                break

            product_urls.update(page_urls)
            print(f"  Page {page}: {len(page_urls)} products found. Total: {len(product_urls)}")
            page += 1
            driver.quit()
            time.sleep(random.uniform(15, 45))  # Longer delay to avoid rate-limiting
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            driver.quit()
            break
        finally:
            try:
                shutil.rmtree(profile_dir)
            except Exception as e:
                print(f"⚠️ Could not remove profile dir {profile_dir}: {e}")

    # Convert set back to list for further processing
    return list(product_urls)

def scrape_product(url, max_retries=3):
    for attempt in range(max_retries):
        user_agent = random.choice(USER_AGENTS)
        profile_dir = os.path.join(os.getcwd(), f"profile_{random.randint(1,10000)}")
        driver = get_chrome_driver(user_agent, profile_dir)
        wait = WebDriverWait(driver, 20)  # Increase wait time
        result = {}
        try:
            driver.get(url)
            time.sleep(random.uniform(5, 15))  # Increase delay
            try:
                title = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'page-title'))).text.strip()
            except:
                print("⚠️ Title not found.")
                title = "N/A"
            try:
                view_more = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'view-more-trigger')))
                if 'View More' in view_more.text:
                    view_more.click()
                    time.sleep(1)
            except:
                pass
            try:
                desc = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'product-description-text')))
                description = desc.get_attribute('innerText').strip()
            except:
                print("⚠️ Description not found.")
                description = "N/A"
            try:
                details = {}
                table = wait.until(EC.presence_of_element_located((By.ID, 'product-attribute-specs-table')))
                rows = table.find_elements(By.TAG_NAME, 'tr')
                for row in rows:
                    try:
                        th = row.find_element(By.TAG_NAME, 'th').text.strip().replace(':', '')
                        td = row.find_element(By.TAG_NAME, 'td').text.strip()
                        details[th] = td
                    except:
                        continue
            except Exception as e:
                print(f"⚠️ Details table not found: {e}")
                details = {}
            result = {
                "Product Title": title,
                "URL": url,
                "Description": description,
                "Details": details
            }
            return result  # Success, return result
        except Exception as e:
            print(f"❌ Error scraping {url} (attempt {attempt+1}): {e}")
            time.sleep(random.uniform(10, 30))  # Wait longer before retry
        finally:
            driver.quit()
            try:
                shutil.rmtree(profile_dir)
            except Exception as e:
                print(f"⚠️ Could not remove profile dir {profile_dir}: {e}")
    print(f"❌ Failed to scrape {url} after {max_retries} attempts. Skipping.")
    return {
        "Product Title": "N/A",
        "URL": url,
        "Description": "N/A",
        "Details": {}
    }

if __name__ == "__main__":
    PARTIAL_CSV = "temporary_export.csv"  # Use this as the final output file

    all_urls = collect_all_product_urls()
    print(f"Total products found: {len(all_urls)}")

    # Resume logic: load already scraped URLs if partial file exists
    if os.path.exists(PARTIAL_CSV):
        partial_df = pd.read_csv(PARTIAL_CSV)
        scraped_urls = set(partial_df['URL'])
        data = partial_df.to_dict('records')
        print(f"Resuming: {len(scraped_urls)} products already scraped.")
    else:
        scraped_urls = set()
        data = []

    urls_to_scrape = [url for url in all_urls if url not in scraped_urls]

    for idx, url in enumerate(urls_to_scrape, start=len(scraped_urls)):
        print(f"[{idx+1}/{len(all_urls)}] Scraping: {url}")
        data.append(scrape_product(url))
        time.sleep(random.uniform(10, 30))
        if (idx+1) % 20 == 0:
            pd.DataFrame(data).to_csv(PARTIAL_CSV, index=False)  # Save progress

    # Save final results to the same file
    if data:
        df = pd.DataFrame(data)
        print("\n🧵 Sample Data Preview:")
        print(df)
        df.to_csv(PARTIAL_CSV, index=False)  # Final save
        print("✅ Final data saved to temporary_export.csv")
    else:
        print("No data scraped.")
