import requests
import csv
import time
from datetime import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://news.ycombinator.com/news"


# Step 3: Fetch the raw HTML of a page
def fetch_page(url):
    headers = {
        # Identify ourselves as a normal browser so the server doesn't block us
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # raises an exception for 4xx/5xx status codes
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


# Step 4: Parse stories out of the raw HTML
def parse_stories(html):
    soup = BeautifulSoup(html, "html.parser")
    stories = []

    # Each story is a <tr class="athing">
    story_rows = soup.find_all("tr", class_="athing")

    for row in story_rows:
        # --- Rank ---
        rank_tag = row.find("span", class_="rank")
        rank = rank_tag.get_text(strip=True).replace(".", "") if rank_tag else "?"

        # --- Title and URL ---
        title_span = row.find("span", class_="titleline")
        if not title_span:
            continue  # skip malformed rows

        link_tag = title_span.find("a")
        title = link_tag.get_text(strip=True) if link_tag else "No title"
        raw_url = link_tag["href"] if link_tag else ""

        # Internal HN links start with "item?id=" — make them absolute
        if raw_url.startswith("item?"):
            raw_url = f"https://news.ycombinator.com/{raw_url}"

        # --- Score, Author, Time (live in the next sibling <tr>) ---
        subtext_row = row.find_next_sibling("tr")
        score, author, posted_time = "N/A", "N/A", "N/A"

        if subtext_row:
            subtext = subtext_row.find("td", class_="subtext")
            if subtext:
                score_tag = subtext.find("span", class_="score")
                score = score_tag.get_text(strip=True) if score_tag else "N/A"

                author_tag = subtext.find("a", class_="hnuser")
                author = author_tag.get_text(strip=True) if author_tag else "N/A"

                age_tag = subtext.find("span", class_="age")
                posted_time = age_tag.get_text(strip=True) if age_tag else "N/A"

        stories.append({
            "rank": rank,
            "title": title,
            "url": raw_url,
            "score": score,
            "author": author,
            "posted": posted_time,
        })

    return stories


# Step 5: Display results in the terminal
def display_stories(stories, page_num=None):
    if page_num:
        print(f"\n  --- Page {page_num} ---")

    for s in stories:
        # Truncate very long titles for cleaner terminal output
        title_display = s["title"][:72] + "..." if len(s["title"]) > 72 else s["title"]
        print(f"\n  [{s['rank']}] {title_display}")
        print(f"       Score: {s['score']}  |  By: {s['author']}  |  Posted: {s['posted']}")
        print(f"       {s['url']}")


# Step 6: Save all stories to a timestamped CSV file
def save_to_csv(stories):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"hn_stories_{timestamp}.csv"
    fieldnames = ["rank", "title", "url", "score", "author", "posted"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(stories)

    return filename


# Step 7: Scrape multiple pages with a polite delay between requests
def scrape_pages(num_pages):
    all_stories = []

    for page_num in range(1, num_pages + 1):
        url = f"{BASE_URL}?p={page_num}"
        print(f"\n  Fetching page {page_num}: {url}")

        html = fetch_page(url)
        if html is None:
            print(f"  Skipping page {page_num} due to fetch error.")
            continue

        stories = parse_stories(html)
        display_stories(stories, page_num)
        all_stories.extend(stories)

        # Be polite — don't hammer the server
        if page_num < num_pages:
            print(f"\n  Waiting 2 seconds before next request...")
            time.sleep(2)

    return all_stories


# Step 8: Main function — ties everything together
def main():
    print("  === Hacker News Scraper ===\n")

    while True:
        try:
            num_pages = int(input("  How many pages to scrape? (1-5 recommended): "))
            if 1 <= num_pages <= 10:
                break
            print("  Please enter a number between 1 and 10.")
        except ValueError:
            print("  Please enter a valid number.")

    all_stories = scrape_pages(num_pages)

    if not all_stories:
        print("\n  No stories were collected. Check your internet connection.")
        return

    filename = save_to_csv(all_stories)

    print(f"\n  {'='*50}")
    print(f"  Scrape complete.")
    print(f"  Total stories collected : {len(all_stories)}")
    print(f"  Saved to               : {filename}")
    print(f"  {'='*50}\n")


# Step 9: Entry point guard
if __name__ == "__main__":
    main()