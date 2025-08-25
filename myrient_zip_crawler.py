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
import argparse

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
                 delay_between_requests: float = 0.5,
                 user_agent: str = None,
                 file_types: str = "zip"):
        # Ensure base_url ends with / for directory crawling
        self.base_url = base_url.rstrip('/') + '/'
        self.max_threads = max_threads
        self.delay_between_requests = delay_between_requests
        
        # Parse file types (comma-separated, no dots)
        self.file_types = [f".{ext.strip().lower()}" for ext in file_types.split(',')]
        
        # Thread-safe collections
        self.visited_urls: Set[str] = set()
        self.zip_urls: Set[str] = set()
        self.url_queue = queue.Queue()
        self.lock = threading.Lock()
        
        # Session with browser-like headers
        self.session = requests.Session()
        
        # Set user agent (default or custom)
        default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        user_agent = user_agent or default_user_agent
        
        self.session.headers.update({
            'User-Agent': user_agent,
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
            
        # Normalize paths for comparison (remove trailing slashes)
        base_path = parsed_base.path.rstrip('/')
        url_path = parsed_url.path.rstrip('/')
        
        # Must be under the base path
        if not url_path.startswith(base_path):
            return False
            
        # Must not go higher than base directory
        base_path_parts = base_path.split('/') if base_path else []
        url_path_parts = url_path.split('/') if url_path else []
        
        if len(url_path_parts) < len(base_path_parts):
            return False
            
        return True
    
    def is_target_file(self, url: str) -> bool:
        """Check if URL points to a target file type."""
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in self.file_types)
    
    def is_directory(self, url: str) -> bool:
        """Check if URL points to a directory (ends with /)."""
        return url.endswith('/')
    
    def should_skip_file(self, url: str) -> bool:
        """Check if file should be skipped (common non-target file types)."""
        # Don't skip files that match our target types
        if self.is_target_file(url):
            return False
            
        skip_extensions = [
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',  # Video files
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a',          # Audio files
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', # Image files
            '.pdf', '.doc', '.docx', '.txt', '.rtf',                  # Document files
            '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm',           # Executable files
            '.iso', '.bin', '.cue', '.img',                           # Disk images
            '.json', '.xml', '.csv', '.sql', '.db', '.sqlite',        # Data files
        ]
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in skip_extensions)
    
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
            
            # Debug logging for URL processing
            logging.debug(f"Processing link: {href} -> {absolute_url}")
            
            # Only include valid URLs
            if self.is_valid_url(absolute_url):
                # If it's a target file, add it to our collection immediately
                if self.is_target_file(absolute_url):
                    with self.lock:
                        self.zip_urls.add(absolute_url)
                    logging.info(f"Found target file: {absolute_url}")
                    continue
                
                # Skip files that are definitely not target files
                if self.should_skip_file(absolute_url):
                    logging.debug(f"Skipping non-target file: {absolute_url}")
                    continue
                    
                # Only add directories to the queue (we'll crawl them later)
                if self.is_directory(absolute_url):
                    links.append(absolute_url)
                    logging.debug(f"Added directory to queue: {absolute_url}")
            else:
                logging.debug(f"Invalid URL (outside scope): {absolute_url}")
                
        return links
    
    def crawl_url(self, url: str):
        """Crawl a single URL and extract links."""
        try:
            # Only make HTTP requests to directories (URLs ending with /)
            if not self.is_directory(url):
                logging.debug(f"Skipping non-directory URL: {url}")
                return
            
            # Add delay to respect rate limits
            time.sleep(self.delay_between_requests + random.uniform(0, 0.2))
            
            logging.info(f"Crawling directory: {url}")
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Log response info for debugging
            logging.debug(f"Response status: {response.status_code}")
            logging.debug(f"Response URL: {response.url}")
            logging.debug(f"Content length: {len(response.text)}")
            
            # Extract links from directory listing
            links = self.extract_links(response.text, url)
            
            # Log directory discovery
            logging.info(f"Gathering URLs from {url}")
            
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
        
        logging.info(f"Crawling completed. Found {len(self.zip_urls)} target files.")
    
    def save_results(self, output_file: str = "myrient_zip_links.txt"):
        """Save ZIP URLs to a text file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in sorted(self.zip_urls):
                f.write(f"{url}\n")
        
        logging.info(f"Saved {len(self.zip_urls)} target file URLs to {output_file}")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Crawl Myrient file repository to find specified file types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python myrient_zip_crawler.py
  python myrient_zip_crawler.py --threads 3 --delay 1.0
  python myrient_zip_crawler.py --filetypes "zip,7z,rar"
  python myrient_zip_crawler.py --user-agent "MyBot/1.0"
        """
    )
    
    parser.add_argument(
        '--threads', '-t',
        type=int,
        default=5,
        help='Number of concurrent threads (default: 5)'
    )
    
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=0.5,
        help='Delay between requests in seconds (default: 0.5)'
    )
    
    parser.add_argument(
        '--user-agent', '-u',
        type=str,
        default=None,
        help='Custom User-Agent string (default: Chrome browser)'
    )
    
    parser.add_argument(
        '--base-url', '-b',
        type=str,
        default="https://myrient.erista.me/files/",
        help='Base URL to start crawling from (default: Myrient files directory)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default="myrient_zip_links.txt",
        help='Output file name (default: myrient_zip_links.txt)'
    )
    
    parser.add_argument(
        '--filetypes', '-f',
        type=str,
        default="zip",
        help='Comma-separated list of file extensions to find (default: zip)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging to see skipped files'
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate arguments
    if args.threads < 1:
        print("Error: Number of threads must be at least 1")
        return
    
    if args.delay < 0:
        print("Error: Delay must be non-negative")
        return
    
    print(f"Starting Myrient File Crawler with:")
    print(f"  Threads: {args.threads}")
    print(f"  Delay: {args.delay}s")
    print(f"  Base URL: {args.base_url}")
    print(f"  File types: {args.filetypes}")
    if args.user_agent:
        print(f"  User-Agent: {args.user_agent}")
    print()
    
    crawler = MyrientZipCrawler(
        base_url=args.base_url,
        max_threads=args.threads,
        delay_between_requests=args.delay,
        user_agent=args.user_agent,
        file_types=args.filetypes
    )
    
    try:
        crawler.crawl()
        crawler.save_results(args.output)
        
        print(f"\nCrawling completed successfully!")
        print(f"Found {len(crawler.zip_urls)} target files")
        print(f"Results saved to: {args.output}")
        
    except KeyboardInterrupt:
        logging.info("Crawling interrupted by user")
        print("\nCrawling interrupted by user")
    except Exception as e:
        logging.error(f"Crawling failed: {e}")
        print(f"\nCrawling failed: {e}")

if __name__ == "__main__":
    main()
