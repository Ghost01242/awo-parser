import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://einrichtungsdatenbank.awo.org"
SEARCH_URL = f"{BASE_URL}/organisations/public-search/-1/-1/-1?Organisations%5Bpage%5D="

def get_details(detail_url):
    response = requests.get(detail_url)
    soup = BeautifulSoup(response.text, 'html.Parser')

    company_name = soup.find('h1', class_='detail-headline').text.strip()
    website = soup.select_one('ul.link-list a')
    company_domain = website['href'].replace("https://", "").replace("www.", "") if website else ""

    email_tag = soup.select_one('div.contact-box a[href^="mailto:"]')
    email = email_tag.text.strip() if email_tag else ""
    email_domain = email.split('@')[1] if "@" in email else ""

    address_tag = soup.select_one('div.panel-heading h4')
    address_parts = address_tag.text.strip().rsplit(',', 1) if address_tag else ["", ""]
    street_address = address_parts[0]
    postal_city = address_parts[1].strip() if len(address_parts) > 1 else ""
    postal_code, city = postal_city.split(' ', 1) if ' ' in postal_city else (postal_city, "")

    tags = [tag.text.strip() for tag in soup.select('.bagfw-cat .text')]
    associated_notes = '; '.join(tags)

    return [company_name, company_domain, email, email_domain, street_address, postal_code, city, associated_notes]


def scrape_organizations(pages=1):
    data = []

    for page in range(1, pages + 1):
        print(f"Scraping page {page}...")
        response = requests.get(SEARCH_URL + str(page))
        soup = BeautifulSoup(response.text, 'html.Parser')

        for panel in soup.select('.panel.panel-primary'):
            detail_link = panel.select_one('.detail-link a')
            if detail_link:
                detail_url = BASE_URL + detail_link['href']
                data.append(get_details(detail_url))
                time.sleep(1)

    return data


data = scrape_organizations(pages=572)
df = pd.DataFrame(data,
                  columns=["Company Name", "Company Domain", "Email", "Email Domain", "Street Address", "Postal Code",
                           "City", "Associated Notes"])
df.to_excel("awo_scraped_data.xlsx", index=False)

print("Scraping complete! Data saved to awo_scraped_data.xlsx")
