#!/usr/bin/env python3
"""
Simple test to check if Myrient site is accessible
"""

import requests

def test_connection():
    urls_to_test = [
        "https://myrient.erista.me/files/",
        "https://myrient.erista.me/",
        "https://erista.me/",
        "http://myrient.erista.me/files/",
        "https://myrient.erista.me/files"
    ]
    
    for url in urls_to_test:
        print(f"\nTesting connection to: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            print(f"Status code: {response.status_code}")
            print(f"Response URL: {response.url}")
            print(f"Content length: {len(response.text)}")
            
            if response.status_code == 200:
                print("✅ Connection successful!")
                print(f"First 200 chars: {response.text[:200]}")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection failed: {e}")
    
    return False

if __name__ == "__main__":
    test_connection()
