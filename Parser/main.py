import csv
import re
import time
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- Setup WebDriver ---
# Configure Chrome options for headless Browse
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

# Install and get the path to the ChromeDriver executable
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)
data = []

# --- Regex for Parsing ---
postal_regex = re.compile(r'(\d{5})\s+(.+)$')
email_regex = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')


# --- Helper Functions ---
def parse_address(address_str):
    """
    Parses a string to extract a 5-digit postal code and city.
    Returns a tuple (postal_code, city) or ("", "").
    """
    match = postal_regex.search(address_str)
    return match.groups() if match else ("", "")


def clean_domain(url):
    """
    Parses a URL and returns the clean domain name (e.g., example.com).
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return "-"

    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def get_total_pages(start_url):
    """
    Navigates to the initial search page and determines the total number of pages.
    """
    driver.get(start_url)
    try:
        pagination_info = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.center-block.pull-right")))
        total_pages_text = pagination_info.text
        # The text is "Seite 1 von X" -> split on ' ' and get the last element (X)
        return int(total_pages_text.split()[-1])
    except Exception as e:
        print(f"[CRITICAL] Could not determine total pages. Starting with page 1. Error: {e}")
        return 1


def parse_page():
    """
    Scrapes data from the current search results page.
    This function now re-locates elements to avoid StaleElementReferenceException.
    It collects essential info from the list view first, then iterates to visit detail pages.
    """

    # 1. Re-find all cards at the beginning of each parse_page call
    # This ensures we have fresh references after any navigation or page changes.
    org_cards_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".panel.panel-primary")))
    print(f"[DEBUG] Found {len(org_cards_elements)} cards on this page.")

    # 2. Collect initial data (title, link, tags, location) from the list view
    # This minimizes interactions with potentially stale elements during subsequent navigation.
    cards_data_for_processing = []
    for i, card_el in enumerate(org_cards_elements):
        company_name_list_view = "-"
        postal_code_list_view = "-"
        city_list_view = "-"
        tags_str_list_view = "-"
        details_link = None

        try:
            # Extract title and location data from specific spans
            title_text = card_el.find_element(By.CSS_SELECTOR, ".panel-heading h3.panel-title").text

            try:
                location_data_span = card_el.find_element(By.CSS_SELECTOR, ".add-loc-data").text.strip()
                postal_code_list_view, city_list_view = parse_address(location_data_span)
                company_name_list_view = title_text.replace(location_data_span, "").strip()
            except NoSuchElementException:
                # Fallback if add-loc-data is not present (e.g., some entries have no address in title)
                company_name_list_view = title_text

            # Extract tags
            tags = [tag.text for tag in card_el.find_elements(By.CSS_SELECTOR, ".badge.badge-pill.badge-primary")]
            tags_str_list_view = "; ".join(tags)

            # Try to find the link to the detail page
            try:
                details_link_el = card_el.find_element(By.CSS_SELECTOR, ".detail-link a")
                details_link = details_link_el.get_attribute("href")
            except NoSuchElementException:
                pass  # No detail link for this card, will be handled below

            cards_data_for_processing.append({
                'company_name_list_view': company_name_list_view,
                'postal_code_list_view': postal_code_list_view,
                'city_list_view': city_list_view,
                'tags_str_list_view': tags_str_list_view,
                'details_link': details_link
            })
        except StaleElementReferenceException:
            # If an element becomes stale *during* this initial loop (less common, but possible)
            print(f"[WARNING] Stale element during initial card data extraction. Retrying page.")
            return False  # Signal that the page needs to be re-parsed

    # 3. Iterate through the collected data to visit detail pages and gather more info
    for card_info in cards_data_for_processing:
        # Initialize variables for detail page data
        email = "-"
        email_domain = "-"
        website = "-"
        website_domain = "-"
        address_detail_page = "-"  # Renamed to avoid confusion with list view address components

        company_name = card_info['company_name_list_view']
        postal_code = card_info['postal_code_list_view']
        city = card_info['city_list_view']
        tags_str = card_info['tags_str_list_view']
        details_link = card_info['details_link']

        try:
            print(f"[DEBUG] Processing organization: {company_name} (Link: {details_link if details_link else 'N/A'})")

            # --- Visit Detail Page if link exists ---
            if details_link and details_link.startswith("http"):
                driver.get(details_link)
                # Wait for the main detail container to ensure the page is loaded
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".container.public-search-detail")))

                # --- Extract Address from detail page ---
                try:
                    # Look for all h4.panel-title elements within the locations section
                    location_titles = driver.find_elements(By.CSS_SELECTOR,
                                                           ".locations .panel-primary .panel-heading .panel-title")

                    if location_titles:
                        # For now, let's just take the first address found
                        address_detail_page = location_titles[0].text.strip()
                        print(f"[DEBUG] Found address using new selector for {company_name}: {address_detail_page}")
                    else:
                        print(f"[DEBUG] No address found in .locations .panel-title for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting address using new selector for {company_name}: {e}")
                    address_detail_page = "-"

                # --- Extract Email and Website ---
                # Based on the HTML, there are multiple places for email/website

                # Attempt 1: From the main headline link list (e.g., "Webseite")
                try:
                    website_el = driver.find_element(By.CSS_SELECTOR, ".headline-wrapper .link-list a[href*='http']")
                    website = website_el.get_attribute("href")
                    website_domain = clean_domain(website)
                    print(f"[DEBUG] Found website in headline-wrapper for {company_name}: {website}")
                except NoSuchElementException:
                    print(f"[DEBUG] No website found in headline-wrapper for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting website from headline-wrapper for {company_name}: {e}")

                # Attempt 2: From the person-detail contact box (for email)
                try:
                    email_el = driver.find_element(By.CSS_SELECTOR, ".person-detail .person-contact a[href^='mailto:']")
                    email = email_el.get_attribute("href").replace("mailto:", "").strip()
                    email_domain = email.split("@")[-1]
                    print(f"[DEBUG] Found email in person-detail for {company_name}: {email}")
                except NoSuchElementException:
                    print(f"[DEBUG] No email found in person-detail for {company_name}.")
                except Exception as e:
                    print(f"[ERROR] Error extracting email from person-detail for {company_name}: {e}")

                # Attempt 3: If website/email not found yet, try looking in the location-specific contact box
                if website == "-" or email == "-":
                    try:
                        location_contact_box = driver.find_element(By.CSS_SELECTOR,
                                                                   ".locations .panel-primary .panel-body .contact-box")

                        if website == "-":  # Only try if not already found
                            try:
                                website_el_loc = location_contact_box.find_element(By.CSS_SELECTOR, "a[href^='http']")
                                website = website_el_loc.get_attribute("href")
                                website_domain = clean_domain(website)
                                print(f"[DEBUG] Found website in location contact box for {company_name}: {website}")
                            except NoSuchElementException:
                                pass  # Not found in this specific box
                            except Exception as e:
                                print(
                                    f"[ERROR] Error extracting website from location contact box for {company_name}: {e}")

                        if email == "-":  # Only try if not already found
                            try:
                                email_el_loc = location_contact_box.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                                email = email_el_loc.get_attribute("href").replace("mailto:", "").strip()
                                email_domain = email.split("@")[-1]
                                print(f"[DEBUG] Found email in location contact box for {company_name}: {email}")
                            except NoSuchElementException:
                                pass  # Not found in this specific box
                            except Exception as e:
                                print(
                                    f"[ERROR] Error extracting email from location contact box for {company_name}: {e}")
                    except NoSuchElementException:
                        print(f"[DEBUG] No location-specific contact box found for {company_name}.")
                    except Exception as e:
                        print(f"[ERROR] Error accessing location contact box for {company_name}: {e}")

                # Go back to the search results page
                driver.back()
                # Wait for the list of cards to be present again on the main search page
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))
                time.sleep(1)  # A small delay can help stabilize the page after back()
            else:
                print(f"[DEBUG] Not visiting detail page for {company_name}. No valid link.")

            # --- Append collected data ---
            # If the address from the detail page is found, update postal_code and city from it
            # This ensures postal code and city are derived from the most accurate full address
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
                "E (Street Address)": address_detail_page,  # Use the address from the detail page
                "F (Postal Code)": postal_code,
                "G (City)": city,
                "J (Tags)": tags_str
            })

        except StaleElementReferenceException:
            print(
                f"[ERROR] Stale element encountered for {company_name if company_name else 'an unknown card'} during processing. This card will be skipped on this iteration.")
            continue  # Skip to the next card in the cards_data_for_processing list
        except Exception as e:
            print(f"[ERROR] General error processing card {company_name if company_name else 'Unknown Card'}: {e}")
            continue

    return True  # Indicate successful parsing of the current page's cards


# --- Main Execution Block ---
start_url = "https://einrichtungsdatenbank.awo.org/organisations/public-search"

try:
    total_pages = get_total_pages(start_url)
    print(f"[INFO] Original total pages: {total_pages}")

    # --- MODIFICATION: Limit to 2 pages for testing. Change this number to scrape more. ---
    pages_to_parse = 2
    print(f"[INFO] Limiting parsing to the first {pages_to_parse} pages for testing.")
    actual_pages_to_parse = min(total_pages, pages_to_parse)

    current_page = 1
    while current_page <= actual_pages_to_parse:
        print(f"\n[INFO] --- Parsing page {current_page}/{actual_pages_to_parse} ---")

        if current_page > 1:
            url = f"{start_url}?Organisations%5Bpage%5D={current_page}"
            driver.get(url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))
            time.sleep(1)  # Small delay for good measure

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
    with open("awo_data.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "A (Company Name)", "B (Company Domain)", "C (Email)", "D (Email Domain)",
            "E (Street Address)", "F (Postal Code)", "G (City)", "J (Tags)"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    print(f"[INFO] Scraping complete. {len(data)} records saved to awo_data.csv")