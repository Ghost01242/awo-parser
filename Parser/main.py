from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import csv
import re
from urllib.parse import urlparse
import time

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)
data = []

postal_regex = re.compile(r'(\d{5})\s+(.+)$')
email_regex = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

def parse_address(address_str):
    match = postal_regex.search(address_str)
    return match.groups() if match else ("", "")

def clean_domain(url):
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return "-"
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

def get_total_pages(start_url):
    driver.get(start_url)
    try:
        pagination_info = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.center-block.pull-right")))
        total_pages_text = pagination_info.text
        return int(total_pages_text.split()[-1])
    except Exception as e:
        print(f"[CRITICAL] Could not determine total pages. Starting with page 1. Error: {e}")
        return 1

def parse_page():
    org_cards_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".panel.panel-primary")))
    print(f"[DEBUG] Found {len(org_cards_elements)} cards on this page.")

    cards_data_for_processing = []
    for i, card_el in enumerate(org_cards_elements):
        company_name_list_view = "-"
        postal_code_list_view = "-"
        city_list_view = "-"
        tags_str_list_view = "-"
        details_link = None

        try:
            title_text = card_el.find_element(By.CSS_SELECTOR, ".panel-heading h3.panel-title").text
            try:
                location_data_span = card_el.find_element(By.CSS_SELECTOR, ".add-loc-data").text.strip()
                postal_code_list_view, city_list_view = parse_address(location_data_span)
                company_name_list_view = title_text.replace(location_data_span, "").strip()
            except NoSuchElementException:
                company_name_list_view = title_text

            tags = [tag.text for tag in card_el.find_elements(By.CSS_SELECTOR, ".badge.badge-pill.badge-primary")]
            tags_str_list_view = "; ".join(tags)

            try:
                details_link_el = card_el.find_element(By.CSS_SELECTOR, ".detail-link a")
                details_link = details_link_el.get_attribute("href")
            except NoSuchElementException:
                pass

            cards_data_for_processing.append({
                'company_name_list_view': company_name_list_view,
                'postal_code_list_view': postal_code_list_view,
                'city_list_view': city_list_view,
                'tags_str_list_view': tags_str_list_view,
                'details_link': details_link
            })
        except StaleElementReferenceException:
            print(f"[WARNING] Stale element during initial card data extraction. Retrying page.")
            return False

    for card_info in cards_data_for_processing:
        email = "-"
        email_domain = "-"
        website = "-"
        website_domain = "-"
        address_detail_page = "-"

        company_name = card_info['company_name_list_view']
        postal_code = card_info['postal_code_list_view']
        city = card_info['city_list_view']
        tags_str = card_info['tags_str_list_view']
        details_link = card_info['details_link']

        try:
            print(f"[DEBUG] Processing organization: {company_name} (Link: {details_link if details_link else 'N/A'})")

            if details_link and details_link.startswith("http"):
                driver.get(details_link)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".container.public-search-detail")))
                try:
                    location_titles = driver.find_elements(By.CSS_SELECTOR, ".locations .panel-primary .panel-heading .panel-title")
                    if location_titles:
                        address_detail_page = location_titles[0].text.strip()
                        print(f"[DEBUG] Found address using new selector for {company_name}: {address_detail_page}")
                    else:
                        print(f"[DEBUG] No address found in .locations .panel-title for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting address using new selector for {company_name}: {e}")
                    address_detail_page = "-"

                try:
                    website_el = driver.find_element(By.CSS_SELECTOR, ".headline-wrapper .link-list a[href*='http']")
                    website = website_el.get_attribute("href")
                    website_domain = clean_domain(website)
                    print(f"[DEBUG] Found website in headline-wrapper for {company_name}: {website}")
                except NoSuchElementException:
                    print(f"[DEBUG] No website found in headline-wrapper for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting website from headline-wrapper for {company_name}: {e}")

                try:
                    email_el = driver.find_element(By.CSS_SELECTOR, ".person-detail .person-contact a[href^='mailto:']")
                    email = email_el.get_attribute("href").replace("mailto:", "").strip()
                    email_domain = email.split("@")[-1]
                    print(f"[DEBUG] Found email in person-detail for {company_name}: {email}")
                except NoSuchElementException:
                    print(f"[DEBUG] No email found in person-detail for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting email from person-detail for {company_name}: {e}")

                if website == "-" or email == "-":
                    try:
                        location_contact_box = driver.find_element(By.CSS_SELECTOR, ".locations .panel-primary .panel-body .contact-box")
                        if website == "-":
                            try:
                                website_el_loc = location_contact_box.find_element(By.CSS_SELECTOR, "a[href^='http']")
                                website = website_el_loc.get_attribute("href")
                                website_domain = clean_domain(website)
                                print(f"[DEBUG] Found website in location contact box for {company_name}: {website}")
                            except NoSuchElementException:
                                pass
                            except Exception as e:
                                print(f"[ERROR] Error extracting website from location contact box for {company_name}: {e}")
                        if email == "-":
                            try:
                                email_el_loc = location_contact_box.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                                email = email_el_loc.get_attribute("href").replace("mailto:", "").strip()
                                email_domain = email.split("@")[-1]
                                print(f"[DEBUG] Found email in location contact box for {company_name}: {email}")
                            except NoSuchElementException:
                                pass
                            except Exception as e:
                                print(f"[ERROR] Error extracting email from location contact box for {company_name}: {e}")
                    except NoSuchElementException:
                        print(f"[DEBUG] No location-specific contact box found for {company_name}.")
                    except Exception as e:
                        print(f"[ERROR] Error accessing location contact box for {company_name}: {e}")

                driver.back()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))
                time.sleep(1)
            else:
                print(f"[DEBUG] Not visiting detail page for {company_name}. No valid link.")

            if address_detail_page != "-":
                temp_postal, temp_city = parse_address(address_detail_page)
                if temp_postal and temp_city:
                    postal_code = temp_postal
                    city = temp_city

            data.append({
                "A (Company Name)": company_name,
                "B (Company Domain)": website_domain,
                "C (Email)": email,
                "D (Email Domain)": email_domain,
                "E (Street Address)": address_detail_page,
                "F (Postal Code)": postal_code,
                "G (City)": city,
                "J (Tags)": tags_str
            })

        except StaleElementReferenceException:
            print(f"[ERROR] Stale element encountered for {company_name if company_name else 'an unknown card'} during processing. This card will be skipped on this iteration.")
            continue
        except Exception as e:
            print(f"[ERROR] General error processing card {company_name if company_name else 'Unknown Card'}: {e}")
            continue

    return True

start_url = "https://einrichtungsdatenbank.awo.org/organisations/public-search"

try:
    total_pages = get_total_pages(start_url)
    print(f"[INFO] Total pages to scrape: {total_pages}")

    current_page = 1
    while current_page <= total_pages:
        print(f"\n[INFO] --- Parsing page {current_page}/{total_pages} ---")

        if current_page > 1:
            url = f"{start_url}?Organisations%5Bpage%5D={current_page}"
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))
            time.sleep(1)

        page_parsed_successfully = False
        try:
            page_parsed_successfully = parse_page()
        except StaleElementReferenceException:
            print(f"[CRITICAL] Entire page {current_page} became stale at start of processing. Retrying this page.")
            page_parsed_successfully = False

        if page_parsed_successfully:
            current_page += 1
        else:
            print(f"[INFO] Retrying page {current_page} due to error.")

except Exception as e:
    print(f"[CRITICAL] An unhandled error occurred during scraping: {str(e)}")

finally:
    driver.quit()
    print("\n[INFO] WebDriver closed. Writing data to CSV.")
    with open("output/awo_data.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "A (Company Name)", "B (Company Domain)", "C (Email)", "D (Email Domain)",
            "E (Street Address)", "F (Postal Code)", "G (City)", "J (Tags)"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"[INFO] Scraping complete. {len(data)} records saved to awo_data.csv")
