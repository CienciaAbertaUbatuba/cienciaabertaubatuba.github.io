# poetry add beautifulsoup4 lxml markdownify PyYAML unidecode
# OR
# pip install beautifulsoup4 lxml markdownify PyYAML unidecode

from bs4 import BeautifulSoup
import os
from markdownify import markdownify as md
import re # For slugify
import yaml # For YAML front matter
from pathlib import Path # For path manipulation
from urllib.parse import urlparse, unquote, urljoin # For link processing
from unidecode import unidecode # For robust accent removal in slugs

def slugify_path_segment(text_segment):
    if text_segment is None: return "default-slug"
    s = str(text_segment).lower()
    s = unidecode(s)
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^\w\-]', '', s)
    s = re.sub(r'\-{2,}', '-', s)
    s = s.strip('-')
    if not s: return "untitled-segment"
    return s

def format_jekyll_date(day, month_str, year):
    if not all([day, month_str, year]): return None
    month_map = {'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'}
    month_normalized = str(month_str).lower()[:3]
    month_num = month_map.get(month_normalized)
    if not month_num: return None
    try: return f"{int(year):04d}-{month_num}-{int(day):02d}"
    except ValueError: return None

def generate_jekyll_permalink_for_path(original_file_path_obj, base_input_dirs_config, base_repo_path_obj):
    try:
        relative_to_repo_root = original_file_path_obj.relative_to(base_repo_path_obj)
        top_level_dir_name = None
        relative_path_after_top_level = None

        for root_name_str in base_input_dirs_config:
            # Check if original_file_path_obj's first part matches a configured root directory name
            if relative_to_repo_root.parts and slugify_path_segment(relative_to_repo_root.parts[0]) == slugify_path_segment(root_name_str):
                top_level_dir_name = slugify_path_segment(root_name_str)
                # Path of parent dir of html file, relative to the top_level_dir_name
                relative_path_after_top_level = Path(*relative_to_repo_root.parts[1:-1])
                break
            # Check if the file itself (slugified stem) matches a configured root item (for top-level files)
            elif slugify_path_segment(relative_to_repo_root.stem) == slugify_path_segment(root_name_str) and relative_to_repo_root.parent == Path("."):
                top_level_dir_name = "" # No top-level dir in permalink for these
                relative_path_after_top_level = Path("")
                break

        if top_level_dir_name is None: # Fallback if not under a known root_slug
            if len(relative_to_repo_root.parts) == 1 : # file in root
                 top_level_dir_name = ""
                 relative_path_after_top_level = Path("")
            else: # some unknown subdirectory, use its slugified name
                top_level_dir_name = slugify_path_segment(relative_to_repo_root.parts[0])
                relative_path_after_top_level = Path(*(slugify_path_segment(p) for p in relative_to_repo_root.parts[1:-1]))

        file_slug = slugify_path_segment(original_file_path_obj.stem)

        path_parts = []
        if top_level_dir_name: path_parts.append(top_level_dir_name)

        if relative_path_after_top_level:
            path_parts.extend([slugify_path_segment(p) for p in relative_path_after_top_level.parts if str(p) != '.'])

        path_parts.append(file_slug) # This is the slug of the file itself, becomes a directory

        return f"/{'/'.join(p for p in path_parts if p)}/"
    except Exception as e:
        print(f"    Error generating permalink for {original_file_path_obj} (relative to {base_repo_path_obj}): {e}")
        return f"/{slugify_path_segment(original_file_path_obj.stem)}/" # Fallback

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
        if not data['title']: data['title'] = current_file_path_obj.stem

        date_div = soup.select_one('div.submitted-date')
        if date_div:
            month_tag = date_div.select_one('div.month'); day_tag = date_div.select_one('div.day'); year_tag = date_div.select_one('div.year')
            if month_tag: data['date_month_str'] = month_tag.get_text(strip=True)
            if day_tag: data['date_day'] = day_tag.get_text(strip=True)
            if year_tag: data['date_year'] = year_tag.get_text(strip=True)
            if data['date_day'] and data['date_month_str'] and data['date_year']: data['is_post'] = True

        author_span = soup.select_one('span.username[property="foaf:name"]')
        if author_span: data['author'] = author_span.get_text(strip=True); data['is_post'] = True

        tag_elements = soup.select('div.field-name-field-tags div.field-item a, div.field.field-name-field-tags.field-type-taxonomy-term-reference ul.links.inline li a')
        if tag_elements: data['tags'] = sorted(list(set([tag.get_text(strip=True) for tag in tag_elements if tag.get_text(strip=True)])))

        content_html_to_process_wrapper = soup.select_one('div.field-item.even[property="content:encoded"]')
        if not content_html_to_process_wrapper:
            main_content_area = soup.select_one('#main .content article .content')
            if not main_content_area: main_content_area = soup.select_one('#main .content')
            if main_content_area and not main_content_area.select_one('.node-teaser'): content_html_to_process_wrapper = main_content_area

        if content_html_to_process_wrapper:
            for el_selector in ['.field-name-field-tags', '#disqus_thread', '.links.inline', 'header', '.post-submitted-info', 'h1#page-title', '.tabs', '.action-links']:
                for el in content_html_to_process_wrapper.select(el_selector): el.decompose()

            youtube_iframe_tag = content_html_to_process_wrapper.select_one('div.field-name-field-video-youtube iframe.youtube-field-player, iframe.youtube-field-player')
            if youtube_iframe_tag:
                parent_field_div = youtube_iframe_tag.find_parent('div', class_='field-name-field-video-youtube')
                if parent_field_div : parent_field_div.extract()
                else: youtube_iframe_tag.extract()
                data['youtube_iframe_html'] = f'<div class="ratio ratio-16x9">{str(youtube_iframe_tag)}</div>'

            # Link transformation
            current_dir_abs_path = current_file_path_obj.parent.resolve()
            for a_tag in content_html_to_process_wrapper.find_all('a', href=True):
                href = a_tag['href']
                parsed_href = urlparse(href)
                if not parsed_href.scheme and not parsed_href.netloc and parsed_href.path.endswith('.html'):
                    target_abs_path = (current_dir_abs_path / Path(unquote(parsed_href.path))).resolve()
                    try:
                        target_repo_relative_path = target_abs_path.relative_to(base_repo_path_obj.resolve())
                        if any(str(target_repo_relative_path).startswith(str(Path(d).name) + os.sep) for d in base_input_dirs_for_permalinks if Path(d).is_dir() and str(Path(d).name) != '.') or \
                           any(target_repo_relative_path == Path(f) for f in base_input_dirs_for_permalinks if Path(f).is_file()):
                            new_permalink = generate_jekyll_permalink_for_path(target_repo_relative_path, base_input_dirs_for_permalinks, base_repo_path_obj)
                            a_tag['href'] = new_permalink
                    except ValueError: pass
                    except Exception as e_link: print(f"    Error processing link {href} in {current_file_abs_path_str}: {e_link}")

            html_for_markdown = content_html_to_process_wrapper.decode_contents()
            if html_for_markdown.strip(): data['main_content_markdown'] = md(html_for_markdown, heading_style='atx', default_title=True, escape_underscores=False, convert=['img'])

        if not data['main_content_markdown'] and not data['youtube_iframe_html']:
            print(f"  Warning: Main content not extracted for {current_file_abs_path_str}.")
            data['main_content_markdown'] = "<!-- Content not found or could not be extracted. Please review original HTML. -->"
        elif data['youtube_iframe_html']:
            if data['main_content_markdown'] and data['main_content_markdown'].strip():
                data['main_content_markdown'] += "\n\n" + data['youtube_iframe_html']
            else:
                data['main_content_markdown'] = data['youtube_iframe_html']

    except Exception as e:
        print(f"  Error during data extraction for {current_file_abs_path_str}: {e}")
        data['title'] = data.get('title') or Path(current_file_abs_path_str).stem
        data['main_content_markdown'] = data.get('main_content_markdown') or ""
    return data

if __name__ == '__main__':
    input_items_to_process_str = ['content'] # User should configure this list
    base_output_dir_str = 'jekyll_site_output' # User can change this

    script_location_dir = Path(__file__).parent.resolve()
    base_output_dir = script_location_dir / base_output_dir_str
    processed_count = 0; error_count = 0

    for item_path_input_str in input_items_to_process_str:
        item_path_obj = script_location_dir / item_path_input_str
        is_file = item_path_obj.is_file()
        is_dir = item_path_obj.is_dir()

        files_to_process_list = []
        if is_dir:
            print(f"\n--- Processing directory: {item_path_obj.relative_to(script_location_dir)} ---")
            for root_str, _, files in os.walk(item_path_obj):
                for filename in files:
                    if filename.endswith(".html"): files_to_process_list.append(Path(root_str) / filename)
        elif is_file:
            files_to_process_list.append(item_path_obj)
        else: print(f"Warning: Item '{item_path_input_str}' not found. Skipping."); continue

        for current_file_path in files_to_process_list:
            print(f"\nProcessing: {current_file_path.relative_to(script_location_dir)}...")
            try:
                with open(current_file_path, 'r', encoding='utf-8') as f: html_content = f.read()
            except Exception as e: print(f"  Error reading file: {e}"); error_count += 1; continue

            extracted_data = extract_page_data(html_content, str(current_file_path), script_location_dir, input_items_to_process_str)
            if not extracted_data.get('title') or "Error extracting title" in extracted_data.get('title', ''): print(f"  Warning: No valid title for {current_file_path}. Skipping."); error_count +=1; continue

            # Determine output path structure
            path_relative_to_script_dir = current_file_path.relative_to(script_location_dir)
            dir_slug = slugify_path_segment(current_file_path.stem)

            if is_dir: # Original item was a directory like 'blog' or 'content'
                original_top_level_dir_name = Path(item_path_input_str).name
                sub_path = current_file_path.parent.relative_to(item_path_obj)
                output_post_dir = base_output_dir / original_top_level_dir_name / sub_path / dir_slug
            else: # Original item was a file like 'ciência-aberta-ubatuba.html'
                output_post_dir = base_output_dir / dir_slug

            output_filepath = output_post_dir / "index.md"

            try: output_post_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e: print(f"  Error creating dir {output_post_dir}: {e}"); error_count += 1; continue

            jekyll_date_str = format_jekyll_date(extracted_data['date_day'], extracted_data['date_month_str'], extracted_data['date_year'])
            front_matter = {'title': extracted_data['title']}
            if extracted_data['is_post'] and jekyll_date_str: front_matter['layout'] = 'post'; front_matter['date'] = jekyll_date_str
            else:
                front_matter['layout'] = 'page'
                if jekyll_date_str: front_matter['date_original_string'] = jekyll_date_str
                elif extracted_data['date_day']: front_matter['date_original_string'] = f"{extracted_data.get('date_year', 'YYYY')}-{extracted_data.get('date_month_str', 'XX')}-{extracted_data.get('date_day', 'XX')}"

            if extracted_data.get('author'): front_matter['author'] = extracted_data['author']
            if extracted_data.get('tags'): front_matter['tags'] = extracted_data['tags']

            front_matter['permalink'] = generate_jekyll_permalink_for_path(path_relative_to_script_dir, input_items_to_process_str, script_location_dir)

            try:
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write('---\n'); yaml.dump(front_matter, f, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper); f.write('---\n\n')
                    f.write(extracted_data.get('main_content_markdown', ''))
                print(f"  Successfully created Jekyll page: {output_filepath}")
                processed_count += 1
            except Exception as e: print(f"  Error writing file {output_filepath}: {e}"); error_count += 1

    print("\n--- Processing Complete ---")
    print(f"Successfully processed and created: {processed_count} file(s).")
    print(f"Encountered errors for: {error_count} file(s).")