import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict
import re
from datetime import datetime
from config import get_openai_client

class DynamicFundingSearcher:
    def __init__(self):
        self.client = get_openai_client()
        self.funding_sources = {
            "foerderdatenbank": {
                "search_url": "https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Foederprogrammsuche_Formular.html",
                "search_params": {
                    "templateQueryString": "KI",
                    "filterCategories": "FundingProgram"
                }
            },
            "nrweuropa": {
                "url": "https://nrweuropa.de/cascadefunding/"
            },
            "isb": {
                "url": "https://isb.rlp.de/service/foerderung.html"
            }
        }
    
    async def search_current_funding(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Dynamically search for current funding opportunities across all sources
        """
        all_results = []
        
        # Generate search keywords from user query
        keywords = await self._extract_search_keywords(query)
        
        # Search each source concurrently
        tasks = [
            self._search_foerderdatenbank(keywords),
            self._search_nrweuropa(keywords),
            self._search_isb(keywords)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source_results in results:
            if isinstance(source_results, list):
                all_results.extend(source_results)
        
        # Rank and filter results based on relevance
        ranked_results = await self._rank_results(all_results, query)
        
        return ranked_results[:max_results]
    
    async def _extract_search_keywords(self, query: str) -> List[str]:
        """Extract relevant search keywords from user query using GPT"""
        prompt = f"""
        Extract 3-5 German search keywords from this funding query that would be most effective 
        for searching German funding databases. Focus on:
        - Technical domains (KI, Robotik, Digitalisierung, etc.)
        - Funding types (Forschung, Innovation, Startup, etc.)
        - Target groups (KMU, Hochschule, etc.)
        
        Query: "{query}"
        
        Return only the German keywords, comma-separated:
        """
        
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        
        keywords_text = response.choices[0].message.content.strip()
        return [k.strip() for k in keywords_text.split(',')]
    
    async def _search_foerderdatenbank(self, keywords: List[str]) -> List[Dict]:
        """Search Förderdatenbank dynamically"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in keywords[:2]:  # Limit to avoid rate limits
                try:
                    search_url = f"https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Foederprogrammsuche_Formular.html?templateQueryString={keyword}"
                    
                    async with session.get(search_url, timeout=10) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Extract funding program links
                            for link_elem in soup.select('p.card--title a')[:3]:  # Top 3 per keyword
                                program_url = link_elem.get('href')
                                if program_url:
                                    program_data = await self._scrape_foerderdatenbank_program(session, program_url)
                                    if program_data:
                                        program_data['source'] = 'foerderdatenbank'
                                        program_data['search_keyword'] = keyword
                                        results.append(program_data)
                
                except Exception as e:
                    print(f"Error searching Förderdatenbank with keyword '{keyword}': {e}")
                    
                await asyncio.sleep(1)  # Rate limiting
        
        return results
    
    async def _scrape_foerderdatenbank_program(self, session: aiohttp.ClientSession, url: str) -> Dict:
        """Scrape individual Förderdatenbank program page"""
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract program details
                    name_elem = soup.find("h1", class_="title")
                    name = name_elem.text.strip() if name_elem else "Unknown Program"
                    
                    desc_elem = soup.find("div", class_="rich--text")
                    description = ""
                    if desc_elem and desc_elem.find("p"):
                        description = desc_elem.find("p").text.strip()
                    
                    # Extract other fields using similar logic to your original scraper
                    domain_dt = soup.find("dt", string=re.compile("Förderbereich"))
                    domain = domain_dt.find_next("dd").text.strip() if domain_dt else ""
                    
                    return {
                        'name': name,
                        'description': description,
                        'domain': domain,
                        'url': url,
                        'scraped_at': datetime.now().isoformat(),
                        'is_current': True
                    }
        except Exception as e:
            print(f"Error scraping program {url}: {e}")
        
        return None
    
    async def _search_nrweuropa(self, keywords: List[str]) -> List[Dict]:
        """Search NRW Europa for current calls"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://nrweuropa.de/cascadefunding/", timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Look for "Open Call" entries
                        strong_tags = soup.find_all("strong", string=lambda text: text and "Open Call" in text)
                        
                        for tag in strong_tags[:5]:  # Limit results
                            try:
                                parent_p = tag.find_parent("p")
                                if parent_p:
                                    full_text = parent_p.get_text(" ", strip=True)
                                    
                                    # Extract structured data
                                    title = tag.get_text(strip=True)
                                    deadline_match = re.search(r"Antragsfrist:\s*([\d\.]+\s+[A-Za-zäöüÄÖÜ]+\s+\d{4})", full_text)
                                    
                                    results.append({
                                        'name': title,
                                        'description': full_text[:300] + "..." if len(full_text) > 300 else full_text,
                                        'deadline': deadline_match.group(1) if deadline_match else None,
                                        'source': 'nrweuropa',
                                        'url': 'https://nrweuropa.de/cascadefunding/',
                                        'scraped_at': datetime.now().isoformat(),
                                        'is_current': True
                                    })
                            except Exception as e:
                                continue
            
            except Exception as e:
                print(f"Error searching NRW Europa: {e}")
        
        return results
    
    async def _search_isb(self, keywords: List[str]) -> List[Dict]:
        """Search ISB for current programs"""
        # Similar implementation to NRW Europa but for ISB
        # Implementation would follow the same pattern
        return []  # Placeholder for now
    
    async def _rank_results(self, results: List[Dict], original_query: str) -> List[Dict]:
        """Rank results based on relevance to original query"""
        if not results:
            return []
        
        # Use GPT to rank results
        results_text = "\n\n".join([
            f"Program {i+1}: {r.get('name', 'Unknown')}\nDescription: {r.get('description', 'No description')[:200]}"
            for i, r in enumerate(results[:10])
        ])
        
        prompt = f"""
        User Query: "{original_query}"
        
        Below are funding programs found from live search. Rank them 1-{len(results[:10])} based on relevance to the user's query.
        Consider domain match, funding stage, and applicability.
        
        {results_text}
        
        Return only the ranking numbers, comma-separated (e.g., "3,1,7,2,5"):
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            
            ranking_text = response.choices[0].message.content.strip()
            rankings = [int(x.strip()) - 1 for x in ranking_text.split(',') if x.strip().isdigit()]
            
            # Reorder results based on ranking
            ranked_results = []
            for rank in rankings:
                if 0 <= rank < len(results):
                    results[rank]['relevance_rank'] = len(ranked_results) + 1
                    ranked_results.append(results[rank])
            
            return ranked_results
            
        except Exception as e:
            print(f"Error ranking results: {e}")
            return results  # Return original order if ranking fails

# Usage function to integrate with existing system
async def get_dynamic_funding_results(query: str, max_results: int = 8) -> List[Dict]:
    """
    Main function to get dynamic funding results
    Can be used alongside or instead of the static Pinecone search
    """
    searcher = DynamicFundingSearcher()
    return await searcher.search_current_funding(query, max_results)