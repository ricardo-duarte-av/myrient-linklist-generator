#!/usr/bin/env python3
"""
Myrient ZIP File Crawler
Crawls https://myrient.erista.me/files/ and subdirectories to find all ZIP files.
Uses threading for speed while respecting rate limits.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import threading
import time
import queue
import re
from pathlib import Path
import logging
from typing import Set, List
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)

class MyrientZipCrawler:
    def __init__(self, base_url: str = "https://myrient.erista.me/files/", 
                 max_threads: int = 5, 
                 delay_between_requests: float = 0.5):
        self.base_url = base_url.rstrip('/')
        self.max_threads = max_threads
        self.delay_between_requests = delay_between_requests
        
        # Thread-safe collections
        self.visited_urls: Set[str] = set()
        self.zip_urls: Set[str] = set()
        self.url_queue = queue.Queue()
        self.lock = threading.Lock()
        
        # Session with browser-like headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Add base URL to queue
        self.url_queue.put(self.base_url)
        
    def is_valid_url(self, url: str) -> bool:
        """Check if URL is within the allowed scope."""
        parsed_base = urlparse(self.base_url)
        parsed_url = urlparse(url)
        
        # Must be same domain
        if parsed_url.netloc != parsed_base.netloc:
            return False
            
        # Must be under the base path
        if not parsed_url.path.startswith(parsed_base.path):
            return False
            
        # Must not go higher than base directory
        base_path_parts = parsed_base.path.strip('/').split('/')
        url_path_parts = parsed_url.path.strip('/').split('/')
        
        if len(url_path_parts) < len(base_path_parts):
            return False
            
        return True
    
    def is_zip_file(self, url: str) -> bool:
        """Check if URL points to a ZIP file."""
        return url.lower().endswith('.zip')
    
    def extract_links(self, html_content: str, current_url: str) -> List[str]:
        """Extract all links from HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Find all anchor tags
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            
            # Skip parent directory links
            if href in ['../', '..']:
                continue
                
            # Convert relative URLs to absolute
            absolute_url = urljoin(current_url, href)
            
            # Only include valid URLs
            if self.is_valid_url(absolute_url):
                links.append(absolute_url)
                
        return links
    
    def crawl_url(self, url: str):
        """Crawl a single URL and extract links."""
        try:
            # Add delay to respect rate limits
            time.sleep(self.delay_between_requests + random.uniform(0, 0.2))
            
            logging.info(f"Crawling: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Check if this is a ZIP file
            if self.is_zip_file(url):
                with self.lock:
                    self.zip_urls.add(url)
                logging.info(f"Found ZIP: {url}")
                return
            
            # Extract links from directory listing
            links = self.extract_links(response.text, url)
            
            # Add new URLs to queue
            for link in links:
                with self.lock:
                    if link not in self.visited_urls:
                        self.visited_urls.add(link)
                        self.url_queue.put(link)
                        
        except requests.RequestException as e:
            logging.error(f"Error crawling {url}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error crawling {url}: {e}")
    
    def worker(self):
        """Worker thread function."""
        while True:
            try:
                url = self.url_queue.get(timeout=5)
                self.crawl_url(url)
                self.url_queue.task_done()
            except queue.Empty:
                break
    
    def crawl(self):
        """Main crawling function."""
        logging.info(f"Starting crawl of {self.base_url}")
        logging.info(f"Using {self.max_threads} threads with {self.delay_between_requests}s delay")
        
        # Start worker threads
        threads = []
        for _ in range(self.max_threads):
            thread = threading.Thread(target=self.worker)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        logging.info(f"Crawling completed. Found {len(self.zip_urls)} ZIP files.")
    
    def save_results(self, output_file: str = "myrient_zip_links.txt"):
        """Save ZIP URLs to a text file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in sorted(self.zip_urls):
                f.write(f"{url}\n")
        
        logging.info(f"Saved {len(self.zip_urls)} ZIP URLs to {output_file}")

def main():
    """Main function."""
    crawler = MyrientZipCrawler(
        base_url="https://myrient.erista.me/files/",
        max_threads=5,  # Conservative threading
        delay_between_requests=0.5  # 500ms delay between requests
    )
    
    try:
        crawler.crawl()
        crawler.save_results()
        
        print(f"\nCrawling completed successfully!")
        print(f"Found {len(crawler.zip_urls)} ZIP files")
        print(f"Results saved to: myrient_zip_links.txt")
        
    except KeyboardInterrupt:
        logging.info("Crawling interrupted by user")
    except Exception as e:
        logging.error(f"Crawling failed: {e}")

if __name__ == "__main__":
    main()
