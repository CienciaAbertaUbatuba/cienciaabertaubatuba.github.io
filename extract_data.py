# poetry add beautifulsoup4 lxml markdownify PyYAML
# OR
# pip install beautifulsoup4 lxml markdownify PyYAML

from bs4 import BeautifulSoup
import os
from markdownify import markdownify as md
import re # For slugify
import yaml # For YAML front matter
from pathlib import Path # For path manipulation

def slugify(text):
    """
    Convert text to a URL-friendly slug.
    Example: "Hello World!" -> "hello-world"
    """
    if text is None:
        return "default-slug"
    text = str(text).lower() # Ensure text is a string
    text = re.sub(r'\s+', '-', text) # Replace spaces with hyphens
    text = re.sub(r'[^\w\-.]', '', text) # Remove non-alphanumeric, allow dots for filename.html
    text = re.sub(r'\-{2,}', '-', text) # Replace multiple hyphens with a single one
    text = text.strip('-') # Remove leading/trailing hyphens
    if not text:
        return "untitled"
    # Remove .html extension if present, for directory naming
    if text.endswith(".html"):
        text = text[:-5]
    return text

def format_jekyll_date(day, month_str, year):
    """
    Formats the date into YYYY-MM-DD for Jekyll.
    Converts month abbreviation (e.g., 'mar') to number.
    """
    if not all([day, month_str, year]):
        # print("Warning: Date components missing, cannot format date.")
        return None # Return None if any component is missing
        
    month_map = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08', 
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }
    month_normalized = str(month_str).lower()[:3] # Ensure month_str is treated as string
    month_num = month_map.get(month_normalized)
    
    if not month_num:
        # print(f"Warning: Could not parse month: {month_str}. Using 'XX' for month.")
        # Return None if month cannot be parsed, so front matter doesn't include invalid date
        return None 
    
    try:
        # Ensure day and year are valid integers and day is padded
        return f"{int(year):04d}-{month_num}-{int(day):02d}"
    except ValueError:
        # print(f"Warning: Could not parse day/year to integer: Day='{day}', Year='{year}'.")
        return None


def extract_page_data(html_content, file_path_for_context=""): # Added file_path for logging
    """
    Extracts specific data from an HTML content.
    Attempts to differentiate between 'post-like' and 'page-like' content.
    """
    soup = BeautifulSoup(html_content, 'lxml')

    data = {
        'title': None,
        'date_month_str': None, # Store original month string
        'date_day': None,
        'date_year': None,
        'author': None,
        'main_content_html': None,
        'main_content_markdown': None, # New field for Markdown
        'tags': [],
        'is_post': False, # Flag to indicate if it's a blog post
        'youtube_iframe_html': None # For storing responsive YouTube iframe
    }

    try:
        # Extract Title
        title_tag = soup.select_one('h1#page-title')
        if title_tag:
            data['title'] = title_tag.get_text(strip=True)
        else: 
            title_tag = soup.select_one('title')
            if title_tag:
                data['title'] = title_tag.get_text(strip=True).split('|')[0].strip()
        
        if not data['title']: # If title is crucial and still not found
             print(f"  Warning: No title found for {file_path_for_context}.")
             data['title'] = Path(file_path_for_context).stem # Use filename as fallback title


        # Extract Date (indicative of a blog post)
        date_div = soup.select_one('div.submitted-date')
        if date_div:
            month_tag = date_div.select_one('div.month')
            if month_tag: data['date_month_str'] = month_tag.get_text(strip=True)
            day_tag = date_div.select_one('div.day')
            if day_tag: data['date_day'] = day_tag.get_text(strip=True)
            year_tag = date_div.select_one('div.year')
            if year_tag: data['date_year'] = year_tag.get_text(strip=True)
            if data['date_day'] and data['date_month_str'] and data['date_year']:
                data['is_post'] = True # Has date, likely a post

        # Extract Author (also indicative of a blog post)
        author_span = soup.select_one('span.username[property="foaf:name"]')
        if author_span:
            data['author'] = author_span.get_text(strip=True)
            if data['author']: data['is_post'] = True 
        
        # Extract Tags
        tag_elements = soup.select('div.field-name-field-tags div.field-item a, div.field.field-name-field-tags.field-type-taxonomy-term-reference ul.links.inline li a')
        if tag_elements:
            data['tags'] = list(set([tag.get_text(strip=True) for tag in tag_elements if tag.get_text(strip=True)])) # Use set to get unique tags


        # --- Main Content and YouTube Iframe Extraction ---
        final_html_parts_for_markdown = []

        # 1. Attempt to find primary content div
        content_div = soup.select_one('div.field-item.even[property="content:encoded"]')
        
        if content_div:
            # Check for YouTube iframe specifically within this content_div
            youtube_iframe_tag = content_div.select_one('iframe.youtube-field-player, div.field-name-field-video-youtube iframe')
            if youtube_iframe_tag:
                # Extract iframe so it's not part of text markdown
                youtube_iframe_tag.extract() 
                responsive_iframe = f'<div class="ratio ratio-16x9">{str(youtube_iframe_tag)}</div>'
                data['youtube_iframe_html'] = responsive_iframe
            
            # Add remaining HTML from content_div (if any)
            html_from_content_div = content_div.decode_contents().strip()
            if html_from_content_div:
                final_html_parts_for_markdown.append(html_from_content_div)
        
        # 2. If no content_div, or as a fallback for other content structures
        if not final_html_parts_for_markdown:
            main_content_area = soup.select_one('#main .content article .content') 
            if not main_content_area: 
                 main_content_area = soup.select_one('#main .content') # More general

            if main_content_area:
                if not main_content_area.select_one('.node-teaser'): # Avoid full index pages
                    # Remove common non-content elements before extracting HTML
                    elements_to_remove_selectors = [
                        '.field-name-field-tags', '#disqus_thread', '.links.inline', 
                        'header', '.post-submitted-info', 'h1#page-title', '.tabs', 
                        '.action-links', 
                        '.field-name-field-video-youtube', # Remove if it's a container already handled or to be handled separately
                        'div.view-agenda table.full', # Specific to agenda page
                        'div.view-agenda div.feed-icon', # Specific to agenda page
                        'div.view-agenda div.view-header' # Specific to agenda page
                    ]
                    for selector in elements_to_remove_selectors:
                        for el in main_content_area.select(selector):
                            el.decompose()
                    
                    html_from_main_area = main_content_area.decode_contents().strip()
                    if html_from_main_area:
                        final_html_parts_for_markdown.append(html_from_main_area)

        # 3. Specifically for video pages, ensure iframe is captured even if not in above selectors
        if not data['youtube_iframe_html']:
            # This selector is specific to the structure found in video content types
            video_iframe_tag = soup.select_one('div.field-name-field-video-youtube iframe.youtube-field-player')
            if video_iframe_tag:
                responsive_iframe = f'<div class="ratio ratio-16x9">{str(video_iframe_tag)}</div>'
                data['youtube_iframe_html'] = responsive_iframe
                # If this is the *only* content (e.g. video page), we might not have text
                # This is fine, the markdown will just be the iframe.

        # Convert accumulated HTML parts to Markdown
        if final_html_parts_for_markdown:
            combined_html = "".join(final_html_parts_for_markdown)
            if combined_html.strip():
                data['main_content_markdown'] = md(combined_html, heading_style='atx', default_title=True, escape_underscores=False)
        
        # Append YouTube iframe HTML to markdown content if it exists
        if data['youtube_iframe_html']:
            if data['main_content_markdown'] and data['main_content_markdown'].strip():
                data['main_content_markdown'] += "\n\n" + data['youtube_iframe_html']
            else:
                data['main_content_markdown'] = data['youtube_iframe_html']
        
        if not data['main_content_markdown']:
             data['main_content_markdown'] = "<!-- Content not found or could not be extracted. Please review original HTML. -->"
             print(f"  Warning: Main content not found or empty for {file_path_for_context}.")

    except Exception as e:
        print(f"  Error during data extraction for {file_path_for_context}: {e}")
        for key_to_check in ['title', 'main_content_markdown']:
            if data.get(key_to_check) is None:
                data[key_to_check] = "" if key_to_check == 'main_content_markdown' else f"Error extracting {key_to_check}"
    return data


if __name__ == '__main__':
    input_dirs_to_process = [
        ('blog', 'dir'),
        ('node', 'dir'),
        ('ciência-aberta-ubatuba.html', 'file'), 
        ('consulta', 'dir'),
        ('video', 'dir')
    ]
    base_output_dir_str = 'jekyll_site_output_v3' # Changed output dir to avoid conflicts

    base_output_dir = Path(base_output_dir_str)
    processed_count = 0
    error_count = 0

    for item_path_str, item_type in input_dirs_to_process:
        item_path_obj = Path(item_path_str)
        
        files_to_process_in_item = []
        current_item_root_for_relative_path = item_path_obj # For dirs, this is the dir itself
        
        if item_type == 'dir':
            if not item_path_obj.is_dir():
                print(f"Warning: Input directory '{item_path_obj}' not found. Skipping.")
                continue
            print(f"\n--- Processing directory: {item_path_obj} ---")
            for root, _, files in os.walk(item_path_obj):
                for filename in files:
                    if filename.endswith(".html"):
                        files_to_process_in_item.append(Path(root) / filename)
        elif item_type == 'file':
            if not item_path_obj.is_file():
                print(f"Warning: Input file '{item_path_obj}' not found. Skipping.")
                continue
            print(f"\n--- Processing file: {item_path_obj} ---")
            files_to_process_in_item.append(item_path_obj)
            # For single files, their parent directory is the root for relative path calculation
            current_item_root_for_relative_path = item_path_obj.parent 


        for current_file_path in files_to_process_in_item:
            print(f"\nProcessing: {current_file_path}...")
            try:
                with open(current_file_path, 'r', encoding='utf-8') as f: html_content = f.read()
            except Exception as e:
                print(f"  Error reading file: {e}"); error_count += 1; continue
            
            extracted_data = extract_page_data(html_content, str(current_file_path))

            if not extracted_data.get('title') or "Error extracting title" in extracted_data.get('title', ''):
                print(f"  Warning: No valid title for {current_file_path}. Skipping."); error_count +=1; continue
            
            # Path logic: base_output_dir / original_toplevel_dir_or_file_stem / relative_subdirs / slugified_filename_as_dir / index.md
            # For top-level files, original_toplevel_dir_or_file_stem is the file's slug.
            # For files in dirs, it's the directory's name (e.g., 'blog', 'node').
            first_level_output_dirname = slugify(item_path_obj.name) if item_type == 'dir' else slugify(item_path_obj.stem)

            relative_dir_from_item_root = current_file_path.parent.relative_to(current_item_root_for_relative_path)
            dir_slug = slugify(current_file_path.stem)
            
            output_post_dir = base_output_dir / first_level_output_dirname / relative_dir_from_item_root / dir_slug
            output_filepath = output_post_dir / "index.md"

            try: output_post_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e: print(f"  Error creating dir {output_post_dir}: {e}"); error_count += 1; continue
            
            jekyll_date_str = format_jekyll_date(extracted_data['date_day'], extracted_data['date_month_str'], extracted_data['date_year'])
            
            front_matter = {'title': extracted_data['title']}
            
            if extracted_data['is_post'] and jekyll_date_str:
                front_matter['layout'] = 'post'
                front_matter['date'] = jekyll_date_str
            else:
                front_matter['layout'] = 'page' 
                if jekyll_date_str: front_matter['date_original_string'] = jekyll_date_str
                elif extracted_data['date_day']: front_matter['date_original_string'] = f"{extracted_data.get('date_year', 'YYYY')}-{extracted_data.get('date_month_str', 'XX')}-{extracted_data.get('date_day', 'XX')}"
            
            if extracted_data.get('author'): front_matter['author'] = extracted_data['author']
            if extracted_data.get('tags'): front_matter['tags'] = extracted_data['tags']
            
            permalink_path_parts = [first_level_output_dirname] + [str(p) for p in relative_dir_from_item_root.parts if str(p) != '.'] + [dir_slug]
            front_matter['permalink'] = f"/{'/'.join(permalink_path_parts)}/"

            try:
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write('---\n'); yaml.dump(front_matter, f, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper); f.write('---\n\n')
                    f.write(extracted_data.get('main_content_markdown', ''))
                print(f"  Successfully created Jekyll page: {output_filepath}")
                processed_count += 1
            except Exception as e: print(f"  Error writing file {output_filepath}: {e}"); error_count += 1
            
    print(f"\n--- Processing Complete ---")
    print(f"Successfully processed and created: {processed_count} file(s).")
    print(f"Encountered errors for: {error_count} file(s).")
