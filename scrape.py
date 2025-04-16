from playwright.sync_api import sync_playwright, Playwright
import re, json,  os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests

load_dotenv()
app = FastAPI()
user_data_dir = "./user-data"

origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Item(BaseModel):
    city: str
    state: str
    zip: int

@app.post("/grabGeolocation")
def grabGeolocation(item: Item):
    city = item.city
    state = item.state
    zip = item.zip

    try:
        resp = requests.get(f"https://geocode.maps.co/search?q={city}%2C+{state}+{zip}&api_key={os.getenv("GEOCODE_API_KEY")}")
        json_data = resp.json()
        loc = json_data[0]
        latitude = float(loc["lat"])
        longitude = float(loc["lon"])

        # run the Shoppers web scraping bot
        scrapeShoppers(latitude, longitude)
        with open("shoppers.json", "r") as f:
            data = json.load(f)
        # json_data = json.dumps(data)

        return data
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)
    
    # return {"Location": f"{item.city}, {item.state} {item.zip}"}

def scrapeShoppers(lat, lon):
    with sync_playwright() as p:
        # basic playwright setup
        chrome = p.chromium
        browser = chrome.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Set geolocation
        context.set_geolocation({ "latitude": lat, "longitude": lon})
        # Grant geolocation
        context.grant_permissions(["geolocation"])


        url = "https://www.shoppersfood.com/search/products?q=eggs"
        page.goto(url)

        selector = "button[data-testid='store-select-link']"
        page.locator(selector).click()

        selector = "button[aria-describedBy='shop2362']"
        page.locator(selector).click()
    

        selector = "div.product-grid"
        productDiv = page.locator(selector)
        children = productDiv.locator("div.product-card")
        print("products: ", children.count())
        eggProducts = []
        price_float = 0.0
        shoppers_dict = {}

        # filter products so I only grab egg cartons + store in json
        for i in range(children.count()):
            child = children.nth(i)
            name = child.locator("div.product-details-wrapper h3").text_content()
            # assuming the price and/or sales price is the first p tag (seems to hold true for the shoppers site as of 4/13/2025)
            price = child.locator("div.product-details-wrapper p").nth(0).text_content() 
        
            extracted_price = (re.search("(\d{1,2}\.\d{2})", price))
            if extracted_price:
                price_float = float(extracted_price[0])
            
            # print out the items that are likely to be an egg carton
            if egg_carton_score(name, 3):
                # json_prod = json.dumps({"name": name, "price": price_float}, indent=2) # python dict -> json string
                eggProducts.append({"name": name, "price": price_float})
                # print(f"Item {i + 1} name: {name} price: ${price_float} ")

        shoppers_dict['products'] = eggProducts
        shoppers_json = json.dumps(shoppers_dict, indent=2)
        with open('shoppers.json', 'w') as f:
            f.write(shoppers_json)

    # input("Press Enter to close the browser...")

# This function takes in a product: string and a threshold: int
# The purpose of this function is to assign a score to the input string
# If the score is >= threshold, there is high likelihood that the string is an egg carton, else there is
# a high likelihood that the string is not an egg carton. 
# This function returns True if the score is >= threshold, else it returns false
def egg_carton_score(product, threshold):
    # strong indicators: +3 points
    # weak indicators: +1 point
    # strong exclusion terms: -3 points
    # weak exclusion terms: -1 point
    strong_indicators = ["Grade AA", "Grade A", "Grade B", "Fresh Eggs", "Free Range"]
    # sizing shouldn't hold too much wait b/c any egg product can have sizes
    weak_indicators = ["Eggs", "Large", "Medium", "Small", "Extra Large", "Jumbo", "12 count", "18 count", "24 count"]
    strong_exclusionary_terms = ["Egg Whites", "Liquid Egg", "Egg Substitute", "Deviled Egg", "Egg White", "Egg Beaters", "Eggplant", "Egg Roll"]
    weak_exclusion_terms = ["Welch's", "Jimmy Dean", "Easter", "Eggo", "Burrito", "Swaggerty's", "Brach's", "Pancakes", "Waffles", "Sausage", "Croissant", "Kellogg's"]
    score = 0
    for term in strong_indicators:
        if term.lower() in product.lower():
            score += 3
    for term in weak_indicators:
        if term.lower() in product.lower():
            score += 1
    for term in strong_exclusionary_terms:
        if term.lower() in product.lower():
            score -= 3
    for term in weak_exclusion_terms:
        if term.lower() in product.lower():
            score -= 1
    
    # print(f"{product}, score: {score}")
    if score >= threshold:
        return True
    return False
