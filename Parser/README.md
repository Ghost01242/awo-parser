# AWO Scraper

A Selenium-based web scraper that collects organization data from the [AWO public database](https://einrichtungsdatenbank.awo.org) and saves it to a CSV file. Wrapped with Docker for easy deployment and isolation.

---

##  Features

- Scrapes:
  - Organization name
  - Email (if available)
  - Website (from multiple locations in the DOM)
  - Physical address
  - Tags
- Outputs data into a CSV file
- Headless Chrome scraping with `selenium` + `webdriver-manager`
- Dockerized for consistent runtime

---

## 📦Technologies

- Python 3.10+
- Selenium
- BeautifulSoup (for testing)
- Docker

---

##  Local Run

```bash
pip install -r requirements.txt
python main.py
