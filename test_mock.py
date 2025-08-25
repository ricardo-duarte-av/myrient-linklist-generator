#!/usr/bin/env python3
"""
Test the crawler logic with mock data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from myrient_zip_crawler import MyrientZipCrawler

def test_crawler_logic():
    """Test the crawler logic with mock HTML data"""
    
    # Mock HTML content that simulates a directory listing
    mock_html = """
    <!DOCTYPE HTML>
    <html>
    <head><title>Index of /files/</title></head>
    <body>
    <h1>Index of /files/</h1>
    <table>
    <tr><td><a href="../">../</a></td></tr>
    <tr><td><a href="No-Intro/">No-Intro/</a></td></tr>
    <tr><td><a href="Redump/">Redump/</a></td></tr>
    <tr><td><a href="TOSEC/">TOSEC/</a></td></tr>
    <tr><td><a href="example.zip">example.zip</a></td></tr>
    <tr><td><a href="archive.7z">archive.7z</a></td></tr>
    <tr><td><a href="video.mp4">video.mp4</a></td></tr>
    <tr><td><a href="document.pdf">document.pdf</a></td></tr>
    </table>
    </body>
    </html>
    """
    
    # Create crawler instance
    crawler = MyrientZipCrawler(base_url="https://myrient.erista.me/files/", file_types="zip,7z")
    
    # Test URL validation
    print("Testing URL validation:")
    test_urls = [
        "https://myrient.erista.me/files/",
        "https://myrient.erista.me/files/No-Intro/",
        "https://myrient.erista.me/files/example.zip",
        "https://myrient.erista.me/files/../",
        "https://othersite.com/files/",
    ]
    
    for url in test_urls:
        is_valid = crawler.is_valid_url(url)
        print(f"  {url}: {is_valid}")
    
    # Test file type detection
    print("\nTesting file type detection:")
    test_files = [
        "https://myrient.erista.me/files/test.zip",
        "https://myrient.erista.me/files/test.mp4",
        "https://myrient.erista.me/files/directory/",
        "https://myrient.erista.me/files/test.7z",
    ]
    
    for url in test_files:
        is_target = crawler.is_target_file(url)
        is_dir = crawler.is_directory(url)
        should_skip = crawler.should_skip_file(url)
        print(f"  {url}: TARGET={is_target}, DIR={is_dir}, SKIP={should_skip}")
    
    # Test link extraction
    print("\nTesting link extraction:")
    links = crawler.extract_links(mock_html, "https://myrient.erista.me/files/")
    print(f"Found {len(links)} links:")
    for link in links:
        print(f"  {link}")
    
    print(f"\nFound {len(crawler.zip_urls)} target files:")
    for target_url in crawler.zip_urls:
        print(f"  {target_url}")

if __name__ == "__main__":
    test_crawler_logic()
