from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import pickle
import os

def get_linkedin_profiles(keyword):
    options = Options()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # Open LinkedIn homepage (to load cookies)
    driver.get("https://www.linkedin.com/")
    time.sleep(3)

    # Load cookies
    if os.path.exists("cookies.pkl"):
        cookies = pickle.load(open("cookies.pkl", "rb"))
        for cookie in cookies:
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
        print("🍪 Cookies loaded successfully")

    # Reload page with session active
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(3)

    # Perform search
    search_url = f"https://www.linkedin.com/search/results/people/?keywords={keyword}"
    driver.get(search_url)
    time.sleep(4)

    profiles = []

    cards = driver.find_elements(By.CSS_SELECTOR, '.reusable-search__result-container')[:5]

    for card in cards:
        try:
            name = card.find_element(By.CSS_SELECTOR, 'span[aria-hidden="true"]').text
        except:
            name = "N/A"
        try:
            title = card.find_element(By.CSS_SELECTOR, '.entity-result__primary-subtitle').text
        except:
            title = "N/A"
        try:
            location = card.find_element(By.CSS_SELECTOR, '.entity-result__secondary-subtitle').text
        except:
            location = "N/A"

        profiles.append({
            'name': name,
            'title': title,
            'location': location,
            'contact': None
        })

    driver.quit()
    return profiles
