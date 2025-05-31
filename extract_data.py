# poetry add beautifulsoup4 lxml markdownify PyYAML unidecode
# OR
# pip install beautifulsoup4 lxml markdownify PyYAML unidecode

from bs4 import BeautifulSoup
import os
from markdownify import markdownify as md
import re
import yaml
from pathlib import Path
from urllib.parse import urlparse, unquote # For link processing
from unidecode import unidecode # For robust accent removal in slugs

def slugify(text):
    if text is None: return "default-slug"
    text = str(text).lower()
    text = unidecode(text) # Convert accented characters to ASCII
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^\w\-.]', '', text) # Remove non-alphanumeric, allow dots for filename.html if still present
    text = re.sub(r'\-{2,}', '-', text)
    text = text.strip('-')
    if not text: return "untitled"
    if text.endswith(".html"): text = text[:-5]
    return text

def format_jekyll_date(day, month_str, year):
    # ... (same as before) ...
    if not all([day, month_str, year]): return None
    month_map = {'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'}
    month_normalized = str(month_str).lower()[:3]
    month_num = month_map.get(month_normalized)
    if not month_num: return None
    try: return f"{int(year):04d}-{month_num}-{int(day):02d}"
    except ValueError: return None

def generate_jekyll_permalink_for_path(original_file_path_obj, base_input_dirs_str_list, script_location_dir=None):
    """
    Generates a Jekyll-style permalink (/path/slug/) for a given original file path object.
    original_file_path_obj: Path object of the source HTML file, relative to script_location_dir.
    base_input_dirs_str_list: List of top-level content directory names or file names (strings)
                              that are being processed (e.g., ['blog', 'node', 'ciencia-aberta-ubatuba.html']).
    script_location_dir: Path object of the directory where the script is running (repo root).
                         If None, original_file_path_obj is assumed to be already relative to repo root.
    """
    try:
        if script_location_dir:
            path_relative_to_repo_root = original_file_path_obj.relative_to(script_location_dir)
        else:
            path_relative_to_repo_root = original_file_path_obj

        parts = list(path_relative_to_repo_root.parts)

        # Check if the path corresponds to a top-level file specified in input_items_to_process_str
        is_top_level_listed_file = str(path_relative_to_repo_root) in base_input_dirs_str_list and \
                                   (script_location_dir / path_relative_to_repo_root if script_location_dir else path_relative_to_repo_root).is_file()


        if is_top_level_listed_file:
            slug = slugify(path_relative_to_repo_root.stem)
            return f"/{slug}/"
        else:
            # Slugify all directory parts and the filename stem for the final slug.
            dir_parts = [slugify(part) for part in parts[:-1]]
            file_slug = slugify(parts[-1])

            final_parts = dir_parts + [file_slug]
            return f"/{'/'.join(final_parts)}/"

    except Exception as e:
        print(f"  Error generating permalink for {original_file_path_obj}: {e}")
        return f"/{slugify(original_file_path_obj.stem)}/"


def extract_page_data(html_content, current_file_abs_path_str, base_repo_path_obj, base_input_dirs_for_permalinks):
    soup = BeautifulSoup(html_content, 'lxml')
    data = {'title': None, 'date_month_str': None, 'date_day': None, 'date_year': None, 'author': None, 'main_content_html': None, 'main_content_markdown': None, 'tags': [], 'is_post': False, 'youtube_iframe_html': None}
    current_file_path_obj = Path(current_file_abs_path_str)

    try:
        title_tag = soup.select_one('h1#page-title')
        if title_tag: data['title'] = title_tag.get_text(strip=True)
        else:
            title_tag = soup.select_one('title')
            if title_tag: data['title'] = title_tag.get_text(strip=True).split('|')[0].strip()
        if not data['title']:
             data['title'] = current_file_path_obj.stem

        date_div = soup.select_one('div.submitted-date')
        if date_div:
            month_tag = date_div.select_one('div.month'); day_tag = date_div.select_one('div.day'); year_tag = date_div.select_one('div.year')
            if month_tag: data['date_month_str'] = month_tag.get_text(strip=True)
            if day_tag: data['date_day'] = day_tag.get_text(strip=True)
            if year_tag: data['date_year'] = year_tag.get_text(strip=True)
            if data['date_day'] and data['date_month_str'] and data['date_year']: data['is_post'] = True

        author_span = soup.select_one('span.username[property="foaf:name"]')
        if author_span:
            data['author'] = author_span.get_text(strip=True)
            if data['author']: data['is_post'] = True

        tag_elements = soup.select('div.field-name-field-tags div.field-item a, div.field.field-name-field-tags.field-type-taxonomy-term-reference ul.links.inline li a')
        if tag_elements: data['tags'] = sorted(list(set([tag.get_text(strip=True) for tag in tag_elements if tag.get_text(strip=True)])))

        content_html_to_process_bs_element = None
        # Try primary content selector
        content_div = soup.select_one('div.field-item.even[property="content:encoded"]')
        if content_div:
            content_html_to_process_bs_element = content_div
        else: # Fallback to more general content area
            main_content_area = soup.select_one('#main .content article .content')
            if not main_content_area: main_content_area = soup.select_one('#main .content')

            if main_content_area:
                if not main_content_area.select_one('.node-teaser'): # Avoid processing index/listing pages as single content
                    # Remove common non-content elements before extracting HTML
                    elements_to_remove_selectors = [
                        '.field-name-field-tags', '#disqus_thread', '.links.inline', 'header',
                        '.post-submitted-info', 'h1#page-title', '.tabs', '.action-links',
                        '.field-name-field-video-youtube', 'div.view-agenda table.full',
                        'div.view-agenda div.feed-icon', 'div.view-agenda div.view-header'
                    ]
                    for selector in elements_to_remove_selectors:
                        for el in main_content_area.select(selector): el.decompose()
                    content_html_to_process_bs_element = main_content_area

        if content_html_to_process_bs_element:
            # Link transformation
            for a_tag in content_html_to_process_bs_element.find_all('a', href=True):
                href = a_tag['href']
                parsed_href = urlparse(href)
                if not parsed_href.scheme and not parsed_href.netloc and parsed_href.path.endswith('.html'): # Relative internal HTML link
                    target_abs_path = (current_file_path_obj.parent / Path(unquote(parsed_href.path))).resolve()
                    try:
                        target_repo_relative_path = target_abs_path.relative_to(base_repo_path_obj.resolve())

                        is_target_in_processed_inputs = False
                        for item_str in base_input_dirs_for_permalinks:
                            abs_item_path_obj = base_repo_path_obj / item_str
                            if abs_item_path_obj.is_dir():
                                if str(target_abs_path).startswith(str(abs_item_path_obj) + os.sep):
                                    is_target_in_processed_inputs = True; break
                            elif target_abs_path == abs_item_path_obj:
                                is_target_in_processed_inputs = True; break

                        if is_target_in_processed_inputs:
                            new_permalink = generate_jekyll_permalink_for_path(target_repo_relative_path, base_input_dirs_for_permalinks, base_repo_path_obj)
                            a_tag['href'] = new_permalink
                    except ValueError: pass
                    except Exception as e_link: print(f"    Error processing link {href} in {current_file_abs_path_str}: {e_link}")


            # Video iframe extraction (from the identified content_html_to_process)
            if not data['youtube_iframe_html']:
                youtube_iframe_tag = content_html_to_process_bs_element.select_one('iframe.youtube-field-player')
                if youtube_iframe_tag:
                    parent_to_extract = youtube_iframe_tag.find_parent('div', class_='field-name-field-video-youtube')
                    if parent_to_extract: parent_to_extract.extract()
                    else: youtube_iframe_tag.extract()
                    responsive_iframe = f'<div class="ratio ratio-16x9">{str(youtube_iframe_tag)}</div>'
                    data['youtube_iframe_html'] = responsive_iframe

            final_html_str = content_html_to_process_bs_element.decode_contents()
            if final_html_str.strip():
                data['main_content_markdown'] = md(final_html_str, heading_style='atx', default_title=True, escape_underscores=False, convert=['img'])


        # If an iframe was found at top level of page (not in content_div) and not already processed
        if not data['youtube_iframe_html']:
            video_field_iframe_container = soup.select_one('div.field-name-field-video-youtube')
            if video_field_iframe_container:
                video_iframe_tag = video_field_iframe_container.select_one('iframe.youtube-field-player')
                if video_iframe_tag:
                    responsive_iframe = f'<div class="ratio ratio-16x9">{str(video_iframe_tag)}</div>'
                    data['youtube_iframe_html'] = responsive_iframe
                    video_field_iframe_container.decompose()

        # Combine textual markdown with iframe markdown
        markdown_content_parts = []
        current_markdown = data.get('main_content_markdown', "")
        if current_markdown and current_markdown.strip() != "<!-- Content not found or could not be extracted. Please review original HTML. -->":
            markdown_content_parts.append(current_markdown)
        if data['youtube_iframe_html']:
            markdown_content_parts.append(data['youtube_iframe_html'])

        if markdown_content_parts:
            data['main_content_markdown'] = "\n\n".join(markdown_content_parts).strip()
        elif not data['youtube_iframe_html']:
             data['main_content_markdown'] = "<!-- Content not found or could not be extracted. Please review original HTML. -->"
             if not data['youtube_iframe_html']:
                print(f"  Warning: Main content and YouTube iframe not found for {current_file_path_obj.name}.")

    except Exception as e:
        print(f"  Major error during data extraction for {current_file_path_obj.name}: {e}")
        for key_to_check in ['title', 'main_content_markdown']:
            if data.get(key_to_check) is None: data[key_to_check] = "" if key_to_check == 'main_content_markdown' else f"Error extracting {key_to_check}"
    return data

if __name__ == '__main__':
    input_items_to_process_str = ['blog', 'node', 'ciência-aberta-ubatuba.html', 'consulta', 'video']
    base_output_dir_str = 'jekyll_site_output'

    script_location_dir = Path(__file__).parent.resolve()
    base_output_dir = script_location_dir / base_output_dir_str

    processed_count = 0; error_count = 0

    for item_path_input_str in input_items_to_process_str:
        item_full_path_obj = script_location_dir / item_path_input_str

        is_file_item = item_full_path_obj.is_file()
        is_dir_item = item_full_path_obj.is_dir()

        files_to_process_list = []

        if is_dir_item:
            print(f"\n--- Processing directory: {item_full_path_obj} ---")
            for root_str, _, files in os.walk(item_full_path_obj):
                root = Path(root_str)
                for filename in files:
                    if filename.endswith(".html"): files_to_process_list.append(root / filename)
        elif is_file_item:
             print(f"\n--- Processing file: {item_full_path_obj} ---")
             files_to_process_list.append(item_full_path_obj)
        else:
            print(f"Warning: Item '{item_full_path_obj}' not found or is not a file/directory. Skipping.")
            continue

        for current_file_abs_path in files_to_process_list:
            print(f"\nProcessing: {current_file_abs_path}...")
            try:
                with open(current_file_abs_path, 'r', encoding='utf-8') as f: html_content = f.read()
            except Exception as e: print(f"  Error reading file {current_file_abs_path}: {e}"); error_count += 1; continue

            extracted_data = extract_page_data(html_content, str(current_file_abs_path), script_location_dir, input_items_to_process_str)
            if not extracted_data.get('title') or "Error extracting title" in extracted_data.get('title', ''): print(f"  Warning: No valid title for {current_file_abs_path}. Skipping."); error_count +=1; continue

            path_relative_to_script = current_file_abs_path.relative_to(script_location_dir)

            output_sub_parts = list(path_relative_to_script.parent.parts)
            output_slug_dir = slugify(path_relative_to_script.stem)

            output_post_dir = base_output_dir.joinpath(*output_sub_parts, output_slug_dir)
            output_filepath = output_post_dir / "index.md"

            try: output_post_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e: print(f"  Error creating dir {output_post_dir}: {e}"); error_count += 1; continue

            jekyll_date_str = format_jekyll_date(extracted_data['date_day'], extracted_data['date_month_str'], extracted_data['date_year'])
            front_matter = {'title': extracted_data['title']}

            if extracted_data['is_post'] and jekyll_date_str:
                front_matter['layout'] = 'post'; front_matter['date'] = jekyll_date_str
            else:
                front_matter['layout'] = 'page'
                if jekyll_date_str: front_matter['date_original_string'] = jekyll_date_str
                elif extracted_data['date_day']: front_matter['date_original_string'] = f"{extracted_data.get('date_year', 'YYYY')}-{extracted_data.get('date_month_str', 'XX')}-{extracted_data.get('date_day', 'XX')}"

            if extracted_data.get('author'): front_matter['author'] = extracted_data['author']
            if extracted_data.get('tags'): front_matter['tags'] = extracted_data['tags']

            front_matter['permalink'] = generate_jekyll_permalink_for_path(path_relative_to_script, input_items_to_process_str, script_location_dir)

            try:
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write('---\n'); yaml.dump(front_matter, f, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper); f.write('---\n\n')
                    f.write(extracted_data.get('main_content_markdown', '').strip())
                print(f"  Successfully created Jekyll page: {output_filepath}")
                processed_count += 1
            except Exception as e: print(f"  Error writing file {output_filepath}: {e}"); error_count += 1

    print(f"\n--- Processing Complete ---")
    print(f"Successfully processed and created: {processed_count} file(s).")
    print(f"Encountered errors for: {error_count} file(s).")
