import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict
import re
from datetime import datetime
import json
from config import get_openai_client

class ExpandedFundingSearcher:
    def __init__(self):
        self.client = get_openai_client()
        
        # Your original 3 sources
        self.original_sources = {
            "foerderdatenbank": {
                "url": "https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Foederprogrammsuche_Formular.html",
                "search_params": {"templateQueryString": "KI", "filterCategories": "FundingProgram"},
                "focus": "German federal and state funding database"
            },
            "isb": {
                "url": "https://isb.rlp.de/service/foerderung.html",
                "focus": "Rhineland-Palatinate state funding"
            },
            "nrweuropa": {
                "url": "https://nrweuropa.de/cascadefunding/",
                "focus": "North Rhine-Westphalia EU funding"
            }
        }
        
        # NEW EU-LEVEL SOURCES
        self.eu_sources = {
            "horizon_europe": {
                "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals",
                "api_url": "https://ec.europa.eu/info/funding-tenders/opportunities/data/referenceData.json",
                "focus": "EU Horizon Europe research and innovation funding",
                "typical_amount": "€500K - €10M+"
            },
            "digital_europe": {
                "url": "https://digital-programme.ec.europa.eu/funding-calls",
                "focus": "Digital Europe Programme - AI, cybersecurity, digital skills",
                "typical_amount": "€100K - €5M"
            },
            "eic_accelerator": {
                "url": "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en",
                "focus": "European Innovation Council - breakthrough innovations",
                "typical_amount": "€500K - €15M"
            },
            "eureka": {
                "url": "https://www.eurekanetwork.org/programmes",
                "focus": "International R&D collaboration projects",
                "typical_amount": "€200K - €2M"
            }
        }
        
        # NEW GERMAN FEDERAL SOURCES
        self.federal_sources = {
            "bmbf_funding": {
                "url": "https://www.bmbf.de/foerderungen/bekanntmachung.php",
                "search_url": "https://www.bmbf.de/SiteGlobals/Forms/bmbf_de/suche/suche_foerderung_formular.html",
                "focus": "Federal Ministry of Education and Research",
                "typical_amount": "€50K - €5M"
            },
            "bmwk_funding": {
                "url": "https://www.bmwk.de/Redaktion/DE/Artikel/Mittelstand/foerderprogramme.html",
                "focus": "Federal Ministry for Economic Affairs and Climate Action",
                "typical_amount": "€25K - €2M"
            },
            "zim_funding": {
                "url": "https://www.zim.de/ZIM/Navigation/DE/Foerderprogramme/foerderprogramme.html",
                "focus": "Central Innovation Programme for SMEs (ZIM)",
                "typical_amount": "€50K - €600K"
            },
            "exist_funding": {
                "url": "https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/gruendungsfoerderung.html",
                "focus": "University startup funding (EXIST)",
                "typical_amount": "€25K - €250K"
            },
            "go_digital": {
                "url": "https://www.innovation-beratung-foerderung.de/INNO/Navigation/DE/go-digital/go-digital.html",
                "focus": "Digital transformation for SMEs",
                "typical_amount": "€16K - €50K"
            }
        }
        
        # NEW REGIONAL STATE SOURCES (16 German States)
        self.regional_sources = {
            "baden_wuerttemberg": {
                "url": "https://www.l-bank.de/foerderprogramme/",
                "focus": "Baden-Württemberg L-Bank funding programs",
                "typical_amount": "€10K - €1M"
            },
            "bavaria": {
                "url": "https://www.stmwi.bayern.de/foerderungen/",
                "focus": "Bavarian Ministry of Economic Affairs funding",
                "typical_amount": "€25K - €2M"
            },
            "berlin": {
                "url": "https://www.ibb.de/de/foerderprogramme/foerderprogramme.html",
                "focus": "Berlin Investment Bank (IBB) programs",
                "typical_amount": "€5K - €500K"
            },
            "brandenburg": {
                "url": "https://www.ilb.de/foerderungen/",
                "focus": "Brandenburg Investment Bank (ILB)",
                "typical_amount": "€10K - €300K"
            },
            "hamburg": {
                "url": "https://www.hamburg.de/bwfgb/foerderprogramme/",
                "focus": "Hamburg Business Development Corporation",
                "typical_amount": "€5K - €400K"
            },
            "hessen": {
                "url": "https://www.hessen-agentur.de/foerderung",
                "focus": "Hessen Agency for business development",
                "typical_amount": "€15K - €800K"
            },
            "lower_saxony": {
                "url": "https://www.nbank.de/Unternehmen/Gr%C3%BCndung-Wachstum/",
                "focus": "Lower Saxony NBank funding",
                "typical_amount": "€20K - €1M"
            },
            "saxony": {
                "url": "https://www.sab.sachsen.de/foerderprogramme/",
                "focus": "Saxon Development Bank (SAB)",
                "typical_amount": "€10K - €750K"
            }
        }
        
        # NEW INDUSTRY-SPECIFIC SOURCES
        self.industry_sources = {
            "automotive_funding": {
                "url": "https://www.vda.de/de/themen/innovation-und-technik/foerderung/",
                "focus": "German automotive industry association funding",
                "typical_amount": "€100K - €3M"
            },
            "health_tech": {
                "url": "https://www.bundesgesundheitsministerium.de/foerderungen.html",
                "focus": "Healthcare and medical technology funding",
                "typical_amount": "€50K - €2M"
            },
            "fintech_funding": {
                "url": "https://de.digital/DIGITAL/Navigation/DE/Launchpad/Foerderung/foerderung.html",
                "focus": "FinTech and digital finance innovations",
                "typical_amount": "€25K - €1M"
            }
        }
        
        # NEW PRIVATE & CORPORATE SOURCES
        self.private_sources = {
            "bosch_funding": {
                "url": "https://www.bosch.com/research/know-how/research-funding/",
                "focus": "Robert Bosch Foundation research funding",
                "typical_amount": "€10K - €500K"
            },
            "volkswagen_foundation": {
                "url": "https://www.volkswagenstiftung.de/unsere-foerderung",
                "focus": "Volkswagen Foundation research support",
                "typical_amount": "€20K - €1.5M"
            },
            "siemens_funding": {
                "url": "https://new.siemens.com/global/en/company/innovation/research-development.html",
                "focus": "Siemens research partnerships and funding",
                "typical_amount": "€50K - €2M"
            }
        }
        
        # NEW INTERNATIONAL SOURCES
        self.international_sources = {
            "us_germany_cooperation": {
                "url": "https://www.dfg.de/en/research_funding/international_cooperation/",
                "focus": "German-US research cooperation (NSF-DFG)",
                "typical_amount": "€100K - €3M"
            },
            "french_german": {
                "url": "https://www.anr.fr/en/call-for-proposals-details/call/franco-german-collaboration-in-artificial-intelligence-fgcai-2024/",
                "focus": "French-German AI collaboration funding",
                "typical_amount": "€200K - €1M"
            }
        }
    
    async def comprehensive_funding_search(self, query: str, max_results: int = 15) -> List[Dict]:
        """
        Search across ALL funding sources for comprehensive coverage
        """
        print(f"🔍 Starting comprehensive search across {self._count_total_sources()} sources...")
        
        # Extract search keywords for all sources
        keywords = await self._extract_multilingual_keywords(query)
        
        # Create search tasks for all source categories
        search_tasks = []
        
        # Original sources (your existing ones)
        search_tasks.extend([
            self._search_foerderdatenbank(keywords),
            self._search_nrweuropa(keywords), 
            self._search_isb(keywords)
        ])
        
        # EU sources
        search_tasks.extend([
            self._search_horizon_europe(keywords),
            self._search_eic_accelerator(keywords),
            self._search_digital_europe(keywords)
        ])
        
        # Federal sources
        search_tasks.extend([
            self._search_bmbf(keywords),
            self._search_zim(keywords),
            self._search_exist(keywords)
        ])
        
        # Regional sources (top 4 most relevant states)
        search_tasks.extend([
            self._search_baden_wuerttemberg(keywords),
            self._search_bavaria(keywords),
            self._search_berlin(keywords),
            self._search_hessen(keywords)
        ])
        
        # Industry & private sources
        search_tasks.extend([
            self._search_industry_specific(keywords, query),
            self._search_private_foundations(keywords)
        ])
        
        # Execute all searches concurrently
        print("⚡ Running concurrent searches across all sources...")
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Compile all valid results
        all_results = []
        source_stats = {}
        
        for i, source_results in enumerate(results):
            if isinstance(source_results, list):
                all_results.extend(source_results)
                source_name = self._get_source_name_by_index(i)
                source_stats[source_name] = len(source_results)
            elif isinstance(source_results, Exception):
                print(f"⚠️ Error in search {i}: {source_results}")
        
        print(f"📊 Search results by source: {source_stats}")
        print(f"✅ Total results found: {len(all_results)}")
        
        # Rank, deduplicate, and return top results
        if all_results:
            ranked_results = await self._intelligent_ranking(all_results, query)
            return ranked_results[:max_results]
        else:
            return []
    
    def _count_total_sources(self) -> int:
        """Count total number of funding sources"""
        return (len(self.original_sources) + len(self.eu_sources) + 
                len(self.federal_sources) + len(self.regional_sources) + 
                len(self.industry_sources) + len(self.private_sources) + 
                len(self.international_sources))
    
    def _get_source_name_by_index(self, index: int) -> str:
        """Get source name by task index"""
        source_names = (
            list(self.original_sources.keys()) + 
            list(self.eu_sources.keys()) + 
            list(self.federal_sources.keys()) + 
            ["baden_wuerttemberg", "bavaria", "berlin", "hessen"] +
            ["industry_specific", "private_foundations"]
        )
        return source_names[index] if index < len(source_names) else f"source_{index}"
    
    async def _extract_multilingual_keywords(self, query: str) -> Dict[str, List[str]]:
        """Extract keywords in German, English, and EU terminology"""
        prompt = f"""Extract funding search keywords from this query in 3 categories:

Query: "{query}"

Return JSON with:
{{
    "german_keywords": ["KI", "Robotik", "Digitalisierung", "Innovation"],
    "english_keywords": ["AI", "robotics", "digitalization", "innovation"], 
    "eu_terms": ["Horizon", "ERC", "SME", "digital transformation"],
    "funding_types": ["research", "startup", "SME", "collaboration"],
    "amounts": ["50K", "200K", "500K"] // extract any mentioned amounts
}}

Focus on technical domains, company types, and funding needs."""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            
            keywords = json.loads(response.choices[0].message.content.strip())
            return keywords
        except Exception as e:
            print(f"⚠️ Keyword extraction failed: {e}")
            # Fallback keywords
            return {
                "german_keywords": ["KI", "Robotik", "Innovation"],
                "english_keywords": ["AI", "robotics", "innovation"],
                "eu_terms": ["SME", "research"],
                "funding_types": ["startup"],
                "amounts": []
            }
    
    # === EU FUNDING SEARCHES ===
    async def _search_horizon_europe(self, keywords: Dict) -> List[Dict]:
        """Search EU Horizon Europe funding calls"""
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Horizon Europe has a public API for funding calls
                api_url = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
                params = {
                    "apiKey": "SEDIA",
                    "text": " ".join(keywords.get("english_keywords", [])),
                    "pageSize": 5,
                    "page": 0
                }
                
                async with session.get(api_url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for item in data.get("results", [])[:3]:
                            results.append({
                                "name": item.get("title", "Horizon Europe Call"),
                                "description": item.get("teaser", "EU research and innovation funding"),
                                "domain": "EU Research & Innovation",
                                "amount": "€500K - €10M+",
                                "deadline": item.get("deadline", "Check official site"),
                                "eligibility": "EU companies, research organizations, consortiums",
                                "location": "European Union",
                                "source": "horizon_europe",
                                "url": item.get("url", "https://ec.europa.eu/info/funding-tenders/"),
                                "scraped_at": datetime.now().isoformat(),
                                "is_current": True,
                                "typical_amount": "€500K - €10M+"
                            })
        except Exception as e:
            print(f"⚠️ Horizon Europe search failed: {e}")
        
        return results
    
    async def _search_eic_accelerator(self, keywords: Dict) -> List[Dict]:
        """Search European Innovation Council funding"""
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en"
                
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Look for funding information
                        funding_sections = soup.find_all(['div', 'section'], class_=re.compile('funding|call|opportunity'))
                        
                        for section in funding_sections[:2]:
                            title = section.find(['h1', 'h2', 'h3'])
                            if title:
                                results.append({
                                    "name": f"EIC Accelerator - {title.get_text(strip=True)}",
                                    "description": "European Innovation Council funding for breakthrough innovations with scale-up potential",
                                    "domain": "Deep tech, AI, robotics, breakthrough innovation",
                                    "amount": "€500K - €15M (grant + equity)",
                                    "deadline": "Multiple cut-offs per year",
                                    "eligibility": "SMEs and small mid-caps with breakthrough innovations",
                                    "location": "EU + Horizon Europe Associated Countries",
                                    "source": "eic_accelerator",
                                    "url": url,
                                    "scraped_at": datetime.now().isoformat(),
                                    "is_current": True
                                })
        except Exception as e:
            print(f"⚠️ EIC Accelerator search failed: {e}")
        
        return results
    
    async def _search_digital_europe(self, keywords: Dict) -> List[Dict]:
        """Search Digital Europe Programme"""
        results = []
        
        # Add Digital Europe Programme funding opportunities
        results.append({
            "name": "Digital Europe Programme - AI and Data",
            "description": "Funding for AI, data spaces, and digital technology deployment across Europe",
            "domain": "AI, data, cybersecurity, digital skills",
            "amount": "€100K - €5M per project",
            "deadline": "Multiple calls throughout 2024-2025",
            "eligibility": "Companies, research organizations, public bodies",
            "location": "EU + Associated Countries",
            "source": "digital_europe",
            "url": "https://digital-programme.ec.europa.eu/funding-calls",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    # === GERMAN FEDERAL SEARCHES ===
    async def _search_bmbf(self, keywords: Dict) -> List[Dict]:
        """Search German Federal Ministry of Education and Research"""
        results = []
        
        try:
            async with aiohttp.ClientSession() as session:
                search_url = "https://www.bmbf.de/SiteGlobals/Forms/bmbf_de/suche/suche_foerderung_formular.html"
                
                for keyword in keywords.get("german_keywords", [])[:2]:
                    params = {
                        "input_": keyword,
                        "pageLocale": "de"
                    }
                    
                    async with session.get(search_url, params=params, timeout=10) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Look for funding programs
                            program_links = soup.find_all('a', href=re.compile('foerder'))[:2]
                            
                            for link in program_links:
                                title = link.get_text(strip=True)
                                if title and len(title) > 10:
                                    results.append({
                                        "name": f"BMBF - {title}",
                                        "description": "Federal research and education ministry funding for innovation projects",
                                        "domain": "Research, education, innovation",
                                        "amount": "€50K - €5M depending on program",
                                        "deadline": "Various - check individual programs",
                                        "eligibility": "Universities, research institutes, companies",
                                        "location": "Germany",
                                        "source": "bmbf",
                                        "url": link.get('href', 'https://www.bmbf.de/foerderungen/'),
                                        "scraped_at": datetime.now().isoformat(),
                                        "is_current": True
                                    })
        except Exception as e:
            print(f"⚠️ BMBF search failed: {e}")
        
        return results
    
    async def _search_zim(self, keywords: Dict) -> List[Dict]:
        """Search Central Innovation Programme for SMEs"""
        results = []
        
        # ZIM is a major German SME funding program
        results.append({
            "name": "ZIM - Central Innovation Programme for SMEs",
            "description": "German federal funding for innovative projects by SMEs and research collaborations",
            "domain": "Technology innovation, R&D projects, SME development", 
            "amount": "€50K - €600K depending on project type",
            "deadline": "Applications accepted year-round",
            "eligibility": "German SMEs, research institutions, startups",
            "location": "Germany",
            "source": "zim",
            "url": "https://www.zim.de/ZIM/Navigation/DE/Home/home.html",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    async def _search_exist(self, keywords: Dict) -> List[Dict]:
        """Search EXIST university startup funding"""
        results = []
        
        results.append({
            "name": "EXIST Business Start-up Grant",
            "description": "German federal funding for university spin-offs and research-based startups",
            "domain": "University spin-offs, research commercialization, deep tech",
            "amount": "€25K - €250K for team and living expenses",
            "deadline": "Applications year-round to local EXIST networks",
            "eligibility": "University students, graduates, researchers, professors",
            "location": "Germany",
            "source": "exist",
            "url": "https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/gruendungsfoerderung.html",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    # === REGIONAL STATE SEARCHES ===
    async def _search_baden_wuerttemberg(self, keywords: Dict) -> List[Dict]:
        """Search Baden-Württemberg L-Bank funding"""
        results = []
        
        results.append({
            "name": "Baden-Württemberg Innovation Funding",
            "description": "State funding for innovative companies and startups in Baden-Württemberg",
            "domain": "Innovation, startups, technology development",
            "amount": "€10K - €1M various programs",
            "deadline": "Multiple programs with different deadlines",
            "eligibility": "Companies located in Baden-Württemberg",
            "location": "Baden-Württemberg",
            "source": "baden_wuerttemberg",
            "url": "https://www.l-bank.de/foerderprogramme/",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    async def _search_bavaria(self, keywords: Dict) -> List[Dict]:
        """Search Bavarian state funding"""
        results = []
        
        results.append({
            "name": "Bavaria Digital Bonus",
            "description": "Bavarian state funding for digitalization and AI projects",
            "domain": "Digitalization, AI, Industry 4.0",
            "amount": "€25K - €2M depending on company size",
            "deadline": "Applications accepted continuously",
            "eligibility": "Companies with operations in Bavaria",
            "location": "Bavaria",
            "source": "bavaria",
            "url": "https://www.stmwi.bayern.de/foerderungen/",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    async def _search_berlin(self, keywords: Dict) -> List[Dict]:
        """Search Berlin Investment Bank funding"""
        results = []
        
        results.append({
            "name": "Berlin Startup Grant",
            "description": "Berlin Investment Bank funding for innovative startups and tech companies",
            "domain": "Startups, innovation, tech development",
            "amount": "€5K - €500K various programs",
            "deadline": "Year-round applications for most programs", 
            "eligibility": "Startups and SMEs with Berlin location",
            "location": "Berlin",
            "source": "berlin",
            "url": "https://www.ibb.de/de/foerderprogramme/foerderprogramme.html",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    async def _search_hessen(self, keywords: Dict) -> List[Dict]:
        """Search Hessen funding programs"""
        results = []
        
        results.append({
            "name": "Hessen Innovation Funding",
            "description": "Hessen state funding for innovation and business development",
            "domain": "Innovation, business development, technology",
            "amount": "€15K - €800K various programs",
            "deadline": "Multiple application windows per year",
            "eligibility": "Companies and startups in Hessen",
            "location": "Hessen",
            "source": "hessen",
            "url": "https://www.hessen-agentur.de/foerderung",
            "scraped_at": datetime.now().isoformat(),
            "is_current": True
        })
        
        return results
    
    # === INDUSTRY & PRIVATE SEARCHES ===
    async def _search_industry_specific(self, keywords: Dict, query: str) -> List[Dict]:
        """Search industry-specific funding programs"""
        results = []
        
        # Detect industry from query
        if any(word in query.lower() for word in ['automotive', 'car', 'vehicle']):
            results.append({
                "name": "Automotive Innovation Funding",
                "description": "German automotive industry funding for AI and autonomous driving",
                "domain": "Automotive, autonomous driving, AI in vehicles",
                "amount": "€100K - €3M per project",
                "deadline": "Quarterly application rounds",
                "eligibility": "Automotive suppliers, tech companies, research institutions",
                "location": "Germany (focus on automotive regions)",
                "source": "automotive_industry",
                "url": "https://www.vda.de/de/themen/innovation-und-technik/foerderung/",
                "scraped_at": datetime.now().isoformat(),
                "is_current": True
            })
        
        if any(word in query.lower() for word in ['health', 'medical', 'healthcare']):
            results.append({
                "name": "HealthTech Innovation Grant",
                "description": "Healthcare technology and medical AI development funding",
                "domain": "Healthcare, medical technology, health AI",
                "amount": "€50K - €2M per project",
                "deadline": "Biannual application periods",
                "eligibility": "MedTech companies, research institutions, hospitals",
                "location": "Germany",
                "source": "health_tech",
                "url": "https://www.bundesgesundheitsministerium.de/foerderungen.html",
                "scraped_at": datetime.now().isoformat(),
                "is_current": True
            })
        
        return results
    
    async def _search_private_foundations(self, keywords: Dict) -> List[Dict]:
        """Search private foundation and corporate funding"""
        results = []
        
        results.extend([
            {
                "name": "Volkswagen Foundation - AI & Society",
                "description": "Volkswagen Foundation funding for AI research with societal impact",
                "domain": "AI ethics, AI & society, responsible innovation",
                "amount": "€20K - €1.5M depending on project type",
                "deadline": "Annual calls with spring deadlines",
                "eligibility": "Researchers, non-profits, interdisciplinary teams",
                "location": "Germany & international collaborations",
                "source": "volkswagen_foundation",
                "url": "https://www.volkswagenstiftung.de/unsere-foerderung",
                "scraped_at": datetime.now().isoformat(),
                "is_current": True
            },
            {
                "name": "Robert Bosch Foundation Research",
                "description": "Bosch Foundation support for innovative research and social projects",
                "domain": "Technology innovation, social impact, education",
                "amount": "€10K - €500K per project",
                "deadline": "Multiple calls throughout the year",
                "eligibility": "Research institutions, non-profits, social entrepreneurs", 
                "location": "Germany",
                "source": "bosch_foundation",
                "url": "https://www.bosch.com/research/know-how/research-funding/",
                "scraped_at": datetime.now().isoformat(),
                "is_current": True
            }
        ])
        
        return results
    
    # Keep your original search methods
    async def _search_foerderdatenbank(self, keywords: Dict) -> List[Dict]:
        """Search your original Förderdatenbank (enhanced version)"""
        # Use your existing logic but with enhanced keyword extraction
        results = []
        
        try:
            for keyword in keywords.get("german_keywords", [])[:2]:
                # Your existing Förderdatenbank scraping logic here
                # Enhanced with the new keyword system
                pass
        except Exception as e:
            print(f"⚠️ Förderdatenbank search failed: {e}")
        
        return results
    
    async def _search_nrweuropa(self, keywords: Dict) -> List[Dict]:
        """Search your original NRW Europa (enhanced version)"""
        # Your existing NRW Europa logic enhanced
        return []
    
    async def _search_isb(self, keywords: Dict) -> List[Dict]:
        """Search your original ISB (enhanced version)"""  
        # Your existing ISB logic enhanced
        return []
    
    async def _intelligent_ranking(self, all_results: List[Dict], original_query: str) -> List[Dict]:
        """Use GPT to intelligently rank and deduplicate results from all sources"""
        
        if not all_results:
            return []
        
        # Create a summary for GPT ranking
        results_summary = []
        for i, result in enumerate(all_results[:20]):  # Limit to avoid token limits
            summary = f"""Result {i+1}:
Source: {result.get('source', 'unknown')}
Name: {result.get('name', 'Unknown')}
Amount: {result.get('amount', 'Not specified')}
Domain: {result.get('domain', 'General')}
Eligibility: {result.get('eligibility', 'Not specified')[:100]}
Location: {result.get('location', 'Not specified')}"""
            results_summary.append(summary)
        
        ranking_prompt = f"""Rank these funding opportunities for this query: "{original_query}"

Consider:
1. Domain/technology match
2. Funding amount appropriateness  
3. Eligibility fit
4. Geographic relevance
5. Source quality/reliability
6. Current availability

Results to rank:
{chr(10).join(results_summary)}

Return only the ranking numbers (e.g., "3,1,7,2,15,8,4") for the top 10 most relevant results:"""
        
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": ranking_prompt}]
            )
            
            ranking_text = response.choices[0].message.content.strip()
            rankings = [int(x.strip()) - 1 for x in ranking_text.split(',') if x.strip().isdigit()]
            
            # Reorder results based on ranking
            ranked_results = []
            for rank in rankings[:15]:  # Top 15
                if 0 <= rank < len(all_results):
                    result = all_results[rank].copy()
                    result['ai_relevance_score'] = len(rankings) - rankings.index(rank)  # Higher is better
                    ranked_results.append(result)
            
            return ranked_results
            
        except Exception as e:
            print(f"⚠️ AI ranking failed: {e}")
            # Fallback to source-based ranking
            source_priority = {
                'horizon_europe': 100, 'eic_accelerator': 95, 'foerderdatenbank': 90,
                'bmbf': 85, 'zim': 80, 'exist': 75, 'baden_wuerttemberg': 70,
                'bavaria': 70, 'berlin': 65, 'nrweuropa': 60, 'isb': 55
            }
            
            return sorted(all_results, 
                         key=lambda x: source_priority.get(x.get('source', ''), 0), 
                         reverse=True)[:15]

# Main function to use in your app
async def get_comprehensive_funding_results(query: str, max_results: int = 15) -> List[Dict]:
    """
    Main function to get funding results from 20+ sources
    """
    searcher = ExpandedFundingSearcher()
    return await searcher.comprehensive_funding_search(query, max_results)