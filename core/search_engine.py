"""
Klein AI - Search Engine and Web Content Extractor
Handles Tavily API multi-aspect research with canonical deduplication, quality filtering,
BS4 DOM content scraping, and DuckDuckGo / Wikipedia fallbacks.
"""
import re
import urllib.parse
from typing import List, Dict, Any, Optional, Set
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.config import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    MAX_SEARCH_RESULTS_PER_QUERY,
    MAX_TOTAL_SOURCES,
    MAX_EXTRACT_CHARS,
    get_tavily_api_key
)

class SearchEngine:
    def __init__(self, tavily_api_key: Optional[str] = None):
        self.tavily_api_key = get_tavily_api_key(tavily_api_key)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    @staticmethod
    def normalize_url(url: str) -> str:
        """Strip tracking parameters, fragments, and normalize canonical URLs."""
        if not url:
            return ""
        try:
            parsed = urllib.parse.urlparse(url)
            # Remove tracking params
            query_params = urllib.parse.parse_qsl(parsed.query)
            clean_params = [(k, v) for k, v in query_params if not k.startswith("utm_") and k not in ("fbclid", "gclid", "ref", "source")]
            clean_query = urllib.parse.urlencode(clean_params)
            
            clean_path = parsed.path.rstrip("/")
            normalized = urllib.parse.urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower().replace("www.", ""),
                clean_path,
                "", # params
                clean_query,
                ""  # fragment
            ))
            return normalized
        except Exception:
            return url.strip().rstrip("/")

    def search_tavily(self, query: str, max_results: int = MAX_SEARCH_RESULTS_PER_QUERY) -> List[Dict[str, Any]]:
        """Search via Tavily API with topic specialization and content summaries."""
        if not self.tavily_api_key:
            return []
        
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self.tavily_api_key)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_raw_content=False,
                include_answer=False
            )
            results = []
            for item in response.get("results", []):
                raw_url = item.get("url", "")
                results.append({
                    "title": item.get("title", "Untitled Source").strip(),
                    "url": raw_url,
                    "canonical_url": self.normalize_url(raw_url),
                    "snippet": item.get("content", "").strip(),
                    "content": item.get("content", "").strip(),
                    "domain": self._extract_domain(raw_url),
                    "engine": "Tavily AI Search",
                    "status": "retrieved"
                })
            return results
        except Exception as e:
            print(f"[SearchEngine] Tavily search notice for '{query}': {e}. Using resilient search fallback.")
            return []

    def search_duckduckgo(self, query: str, max_results: int = MAX_SEARCH_RESULTS_PER_QUERY) -> List[Dict[str, Any]]:
        """Fallback search using DuckDuckGo / ddgs (no API key required)."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=max_results))
                for item in ddg_results:
                    raw_url = item.get("href", "")
                    results.append({
                        "title": item.get("title", "Web Source").strip(),
                        "url": raw_url,
                        "canonical_url": self.normalize_url(raw_url),
                        "snippet": item.get("body", "").strip(),
                        "content": item.get("body", "").strip(),
                        "domain": self._extract_domain(raw_url),
                        "engine": "DuckDuckGo",
                        "status": "retrieved"
                    })
            return results
        except Exception as e:
            return []

    def search_wikipedia(self, query: str, max_results: int = MAX_SEARCH_RESULTS_PER_QUERY) -> List[Dict[str, Any]]:
        """Reliable academic fallback via Wikipedia API (guarantees real public encyclopedic & technical sources)."""
        try:
            url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            if resp.status_code != 200:
                return []
            data = resp.json()
            search_items = data.get("query", {}).get("search", [])[:max_results]
            results = []
            for item in search_items:
                raw_snippet = item.get("snippet", "")
                clean_snippet = re.sub(r"<.*?>", "", raw_snippet).strip()
                title = item.get("title", "").strip()
                wiki_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                results.append({
                    "title": title,
                    "url": wiki_url,
                    "canonical_url": self.normalize_url(wiki_url),
                    "snippet": clean_snippet,
                    "content": clean_snippet,
                    "domain": "en.wikipedia.org",
                    "engine": "Wikipedia Scholarly Knowledge",
                    "status": "retrieved"
                })
            return results
        except Exception as e:
            return []

    def search_query(self, query: str, max_results: int = MAX_SEARCH_RESULTS_PER_QUERY) -> List[Dict[str, Any]]:
        """Multi-tier search: Tavily AI -> DuckDuckGo -> Wikipedia Scholarly."""
        results = []
        if self.tavily_api_key:
            results = self.search_tavily(query, max_results=max_results)
            
        if not results:
            results = self.search_duckduckgo(query, max_results=max_results)

        if not results:
            results = self.search_wikipedia(query, max_results=max_results)
            
        return results

    def extract_page_content(self, url: str) -> str:
        """
        Extract clean readable text from a webpage using BeautifulSoup4.
        Strips navigational chrome, scripts, ads, headers, footers, and cookie banners.
        """
        if not url or not url.startswith("http"):
            return ""
        
        try:
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT, verify=False)
            if resp.status_code != 200:
                return ""
            
            content_type = resp.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ""

            soup = BeautifulSoup(resp.content, "html.parser")

            # Remove non-content tags
            for elem in soup([
                "script", "style", "nav", "footer", "header", "aside", "form",
                "svg", "noscript", "iframe", "dialog", "button", "figure"
            ]):
                elem.extract()

            # Remove cookie notices and ads by class/id patterns
            ad_patterns = re.compile(r"cookie|banner|advert|popup|modal|newsletter|social-share|sidebar", re.I)
            for junk in soup.find_all(attrs={"class": ad_patterns}):
                junk.decompose()
            for junk in soup.find_all(attrs={"id": ad_patterns}):
                junk.decompose()

            # Prefer main article container
            main_elem = (
                soup.find("article") or
                soup.find("main") or
                soup.find("div", {"id": re.compile(r"content|main|article|body|post-body", re.I)}) or
                soup.find("div", {"class": re.compile(r"article-content|entry-content|post-content", re.I)}) or
                soup.body or
                soup
            )

            # Extract clean paragraphs
            paragraphs = main_elem.find_all(["p", "h1", "h2", "h3", "h4", "li"])
            if paragraphs:
                text_blocks = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
                cleaned_text = "\n\n".join(text_blocks)
            else:
                text = main_elem.get_text(separator="\n")
                lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 25]
                cleaned_text = "\n".join(lines)
            
            # Truncate to avoid context window explosion
            if len(cleaned_text) > MAX_EXTRACT_CHARS:
                cleaned_text = cleaned_text[:MAX_EXTRACT_CHARS] + "\n...[Source content truncated for analysis]"
            return cleaned_text
        except Exception:
            return ""

    def execute_multi_aspect_search(
        self,
        queries_with_aspects: List[Dict[str, str]],
        max_total: int = MAX_TOTAL_SOURCES,
        enrich_content: bool = True,
        log_callback=None
    ) -> List[Dict[str, Any]]:
        """
        Executes multi-aspect search with intelligent canonical deduplication,
        source quality scoring, and graceful failure handling.
        """
        seen_canonical_urls: Set[str] = set()
        seen_titles: Set[str] = set()
        all_sources: List[Dict[str, Any]] = []

        for item in queries_with_aspects:
            if len(all_sources) >= max_total:
                break
                
            query = item.get("query", "")
            aspect = item.get("aspect", "General")
            if not query:
                continue
                
            if log_callback:
                log_callback(f"🔎 [{aspect}] Searching: '{query}'")
                
            results = self.search_query(query, max_results=MAX_SEARCH_RESULTS_PER_QUERY)
            
            added_from_query = 0
            for res in results:
                can_url = res.get("canonical_url") or self.normalize_url(res.get("url", ""))
                title_norm = re.sub(r"[^\w\s]", "", res.get("title", "").lower()).strip()
                
                # Check for duplication across URL and title
                if not can_url or can_url in seen_canonical_urls or title_norm in seen_titles:
                    continue
                    
                seen_canonical_urls.add(can_url)
                seen_titles.add(title_norm)
                res["aspect"] = aspect
                all_sources.append(res)
                added_from_query += 1
                
                if len(all_sources) >= max_total:
                    break

        if log_callback:
            log_callback(f"📥 Collected {len(all_sources)} deduplicated candidate sources across aspects.")

        # Deep Content Extraction & Quality Filtering
        if enrich_content:
            valid_sources = []
            for idx, source in enumerate(all_sources):
                url = source.get("url")
                domain = source.get("domain", "web")
                
                if log_callback and (idx + 1) % 2 == 0:
                    log_callback(f"📄 Scraping & verifying DOM text: {domain}")
                    
                extracted = self.extract_page_content(url)
                if extracted and len(extracted) > len(source.get("snippet", "")):
                    source["content"] = extracted
                    source["extraction_status"] = "Full Content Extracted"
                else:
                    source["extraction_status"] = "Snippet Preserved"
                    
                # Rate source quality
                content_len = len(source.get("content", ""))
                if content_len > 1000 or any(a in domain for a in ["ncbi", "ieee", "acm", "arxiv", "edu", "gov"]):
                    source["quality_badge"] = "High Quality / Academic"
                elif content_len > 300:
                    source["quality_badge"] = "Medium Quality"
                else:
                    source["quality_badge"] = "Low Quality / Brief"
                    
                valid_sources.append(source)
            all_sources = valid_sources

        if log_callback:
            log_callback(f"✅ Web research extraction completed. {len(all_sources)} validated sources ready.")

        return all_sources

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain if domain else "web-source"
        except Exception:
            return "web-source"
