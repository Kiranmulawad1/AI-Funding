import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re

async def scrape_nrweuropa():
    url = "https://nrweuropa.de/cascadefunding/"
    funding_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    strong_tags = soup.find_all("strong", string=lambda text: text and "Open Call" in text)

    for tag in strong_tags:
        title = tag.get_text(strip=True)
        parent_p = tag.find_parent("p")
        if not parent_p:
            continue

        # Combine paragraph and nearby content
        full_text = parent_p.get_text(" ", strip=True)
        for i, sibling in enumerate(parent_p.next_siblings):
            if i >= 5:
                break
            if hasattr(sibling, "get_text"):
                full_text += " " + sibling.get_text(" ", strip=True)

        # Extract fields using regex
        extract = lambda pattern: re.search(pattern, full_text)
        topic = extract(r"Thema:\s*(.*?)\s*(Förderfähig:|Budget:|Antragsfrist:|$)")
        eligibility = extract(r"Förderfähig:\s*(.*?)\s*(Budget:|Antragsfrist:|$)")
        budget = extract(r"Budget:\s*(.*?)\s*(Antragsfrist:|$)")
        deadline = extract(r"Antragsfrist:\s*([\d\.]+\s+[A-Za-zäöüÄÖÜ]+\s+\d{4})")

        topic = topic.group(1).strip() if topic else None
        eligibility = eligibility.group(1).strip() if eligibility else None
        budget = budget.group(1).strip() if budget else None
        deadline = deadline.group(1).strip() if deadline else None

        # Clean description
        description = full_text
        for label, val in {
            "Thema:": topic,
            "Förderfähig:": eligibility,
            "Budget:": budget,
            "Antragsfrist:": deadline,
            title: title
        }.items():
            if val:
                description = description.replace(f"{label} {val}", "")
        description = description.replace(title, "").strip()

        # Extract URL
        url_link = next((a.get("href") for a in parent_p.find_all("a") if a.get("href")), None)
        if not url_link:
            for i, sibling in enumerate(parent_p.next_siblings):
                if i >= 5:
                    break
                if hasattr(sibling, "find"):
                    a = sibling.find("a")
                    if hasattr(a, "get"):
                        href = a.get("href")
                        if href and href.strip():
                            url_link = href
                            break

        funding_data.append({
            "Name": title,
            "Topic": topic,
            "Eligibility": eligibility,
            "Budget": budget,
            "Deadline": deadline,
            "Description": description,
            "URL": url_link,
            "Source": "NRW Europa",
            "Language": "de",
            "Translated": False
        })

    return pd.DataFrame(funding_data)

# Entry point
if __name__ == "__main__":
    df = asyncio.run(scrape_nrweuropa())
    df.to_csv("nrw_europa_funding.csv", index=False)
    print("Saved to nrw_europa_funding.csv")
