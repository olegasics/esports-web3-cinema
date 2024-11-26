import requests
import time
import logging
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

app = FastAPI()

origins = ["http://localhost:8001"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Match(BaseModel):
    team1: str
    team2: str
    time: str


class Tournament(BaseModel):
    name: str
    date: str
    link: str
    upcoming_matches: list[Match]


class LiquipediaScraper:
    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    ):
        self.user_agent = user_agent

    def get_article_html(self, page: str):
        url = "https://liquipedia.net/counterstrike/api.php"

        params = {"action": "parse", "page": page, "format": "json"}
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"}

        time.sleep(3)
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            try:
                data = response.json()
                logger.debug(
                    "API response data: %s", data
                )  # Log the response data for debugging
                if "parse" in data and "text" in data["parse"]:
                    return data["parse"]["text"]["*"]
                else:
                    logger.warning("Unexpected response structure: %s", data)
                    return None
            except ValueError as e:
                logger.error("Error parsing JSON: %s", e)
                return None
        else:
            logger.error(
                "Error fetching page: %s %s", response.status_code, response.text
            )
            response.raise_for_status()

    def parse_upcoming_tournaments(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        tournaments_list = soup.find("ul", class_="tournaments-list")
        tournaments = []

        if not tournaments_list:
            print("Tournaments list not found.")
            return tournaments

        # Find the first block with the specified attributes
        first_block = tournaments_list.find(
            "li", attrs={"data-filter-hideable-group": True, "data-filter-effect": True}
        )

        if not first_block:
            print("First block with specified attributes not found.")
            return tournaments

        tournament_entries = first_block.find_all("li")

        if not tournament_entries:
            print("Tournament entries not found.")
            return tournaments

        for entry in tournament_entries:
            tournament_name_tag = entry.find("a", title=True)
            date_tag = entry.find("small", class_="tournaments-list-dates")

            if tournament_name_tag and date_tag:
                tournament_name = tournament_name_tag.get("title")
                tournament_link = tournament_name_tag.get("href")
                tournament_date = date_tag.text.strip()

                if "Romanian_Esports_League" not in tournament_link:
                    continue

                final_link = tournament_link.replace("/counterstrike/", "")
                html_content = self.get_article_html(final_link)

                matches = self.parse_upcoming_matches(html_content)

                tournaments.append(
                    Tournament(**{
                        "name": tournament_name,
                        "link": tournament_link,
                        "date": tournament_date,
                        "upcoming_matches": matches,
                    })
                )
                print(
                    f"Tournament: {tournament_name}, Date: {tournament_date}, Link: {tournament_link}"
                )

        return tournaments

    def parse_upcoming_matches(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        matches_table = soup.find(
            "div", class_="fo-nttax-infobox wiki-bordercolor-light"
        )

        if not matches_table:
            print("Matches table not found.")
            return []

        matches_lists = matches_table.find_all(
            "table", class_="wikitable wikitable-striped infobox_matches_content"
        )  # Use find_all to get all tables
        matches = []

        if not matches_lists:
            print("Matches lists not found.")
            return matches

        for matches_list in matches_lists:
            for row in matches_list.find_all("tr"):
                teams = row.find_all("td", class_=["team-left", "team-right"])
                if len(teams) == 2:
                    team1 = teams[0].get_text(strip=True)
                    team2 = teams[1].get_text(strip=True)
                    match_time = (
                        row.find("span", class_="timer-object-date").get_text(
                            strip=True
                        )
                        if row.find("span", class_="timer-object-date")
                        else "N/A"
                    )
                    match_info = Match(**{
                        "team1": team1,
                        "team2": team2,
                        "time": match_time,
                    })
                    matches.append(match_info)

        return matches
        # return [{"team1": "test", "team2": "test", "time": "test"}]


@app.get("/get_upcoming_tournaments/")
def get_upcoming_tournaments():
    scraper = LiquipediaScraper()
    html_content = scraper.get_article_html("Main_Page")
    tournaments = scraper.parse_upcoming_tournaments(html_content)

    return tournaments


@app.get("/get_upcoming_matches/")
def get_upcoming_matches(link: str) -> list[Match]:
    final_link = link.replace("/counterstrike/", "")
    scraper = LiquipediaScraper()
    html_content = scraper.get_article_html(final_link)

    matches = scraper.parse_upcoming_matches(html_content)
    # matches = scraper.parse_upcoming_matches("")

    return matches
