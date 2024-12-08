import json
from typing import List, Dict
import argparse
import ftfy

def clean_news_data(input_file: str, output_file: str) -> None:
    """
    Clean news data by:
    1. Removing entries without required fields
    2. Removing duplicates based on title and link
    3. Ensuring data quality
    4. Fixing encoding issues using ftfy
    """
    print(f"Reading data from {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
        return
    except json.JSONDecodeError:
        print(f"Error: File {input_file} is not valid JSON")
        return

    print(f"Initial number of entries: {len(data)}")

    # Fix encoding for all text fields using ftfy
    for item in data:
        for key in ['title', 'content', 'link']:
            if key in item and isinstance(item[key], str):
                item[key] = ftfy.fix_text(item[key]).strip()

    # Step 1: Filter entries with required fields
    required_fields = ['image_url', 'title', 'content', 'link']
    valid_data = [
        item for item in data 
        if all(key in item and item[key] and isinstance(item[key], str) 
        for key in required_fields)
    ]
    
    print(f"Entries after required fields check: {len(valid_data)}")

    # Step 2: Remove duplicates while keeping the first occurrence
    seen_titles = set()
    seen_links = set()
    unique_data = []

    for item in valid_data:
        # Normalize strings for comparison
        title = item['title'].strip().lower()
        link = item['link'].strip().lower()
        
        if title not in seen_titles and link not in seen_links:
            seen_titles.add(title)
            seen_links.add(link)
            unique_data.append(item)

    print(f"Final number of entries after removing duplicates: {len(unique_data)}")

    # Step 3: Save cleaned data
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_data, f, ensure_ascii=False, indent=4)
        print(f"Cleaned data saved to {output_file}")
        
        # Print summary
        print("\nSummary:")
        print(f"Total entries removed: {len(data) - len(unique_data)}")
        print(f"Entries removed due to missing fields: {len(data) - len(valid_data)}")
        print(f"Duplicate entries removed: {len(valid_data) - len(unique_data)}")
        
    except Exception as e:
        print(f"Error saving output file: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Clean news data JSON file')
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument(
        '--output', 
        '-o', 
        default='cleaned_news.json',
        help='Output JSON file path (default: cleaned_news.json)'
    )

    args = parser.parse_args()
    clean_news_data(args.input_file, args.output)

if __name__ == "__main__":
    main() 