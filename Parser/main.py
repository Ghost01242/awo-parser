from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import csv
import re
from urllib.parse import urlparse

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
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

def parse_page():
    org_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".panel.panel-primary")))

    for card in org_cards:
        try:
            title = card.find_element(By.CSS_SELECTOR, ".panel-title").text
            postal_code, city = parse_address(title.split()[-2] + " " + title.split()[-1])

            tags = [tag.text for tag in card.find_elements(By.CSS_SELECTOR, ".badge.badge-pill.badge-primary")]
            tag_str = "; ".join(tags)

            details_link = card.find_element(By.CSS_SELECTOR, ".btn.btn-primary").get_attribute("href")
            driver.get(details_link)

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel-body")))

            email = "-"
            email_domain = "-"
            website = "-"
            address = "-"

            try:
                contact_info = driver.find_element(By.CSS_SELECTOR, ".panel-body").text
                email_match = email_regex.search(contact_info)
                if email_match:
                    email = email_match.group(0)
                    email_domain = email.split("@")[-1]

                website_el = driver.find_element(By.CSS_SELECTOR, "a[href^='http']")
                website = website_el.get_attribute("href")
            except:
                pass

            website_domain = clean_domain(website) if website != "-" else "-"

            try:
                address = driver.find_element(By.XPATH, "//dt[contains(text(), 'Anschrift')]/following-sibling::dd").text.strip()
            except:
                pass

            data.append({
                "A (Company Name)": " ".join(title.split()[:-2]),
                "B (Company Domain)": website_domain,
                "C (Email)": email,
                "D (Email Domain)": email_domain,
                "E (Street Address)": address,
                "F (Postal Code)": postal_code,
                "G (City)": city,
                "J (Tags)": tag_str
            })

            driver.back()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))

        except Exception as e:
            print(f"Ошибка: {str(e)}")
            continue

def get_total_pages():
    driver.get("https://einrichtungsdatenbank.awo.org/organisations/public-search")
    pagination_info = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "p.center-block.pull-right")))
    return int(pagination_info.text.split()[-1])

try:
    total_pages = get_total_pages()

    for current_page in range(1, total_pages + 1):
        print(f"Парсинг страницы {current_page}/{total_pages}")

        if current_page > 1:
            url = f"https://einrichtungsdatenbank.awo.org/organisations/public-search?Organisations%5Bpage%5D={current_page}"
            driver.get(url)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-primary")))
        parse_page()

except Exception as e:
    print(f"Ошибка: {str(e)}")

finally:
    driver.quit()
    with open("awo_data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["A (Company Name)", "B (Company Domain)", "C (Email)", "D (Email Domain)",
                                               "E (Street Address)", "F (Postal Code)", "G (City)", "J (Tags)"])
        writer.writeheader()
        writer.writerows(data)

print("Парсинг завершен. Данные сохранены в awo_data.xlsx")
