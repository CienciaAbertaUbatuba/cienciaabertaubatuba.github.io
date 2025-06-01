import os
import re
import yaml
from pathlib import Path
from urllib.parse import urlparse, unquote
from unidecode import unidecode

# --- Configuration (You might need to adjust these) ---
CONTENT_BASE_DIR = '.'
# KNOWN_CONTENT_ROOT_SLUGS should list the names of the directories in CONTENT_BASE_DIR
# that contain the Jekyll content (e.g., 'blog', 'node', 'video', 'consulta')
# AND the actual directory names for any top-level pages that were converted into page-specific directories
# (e.g., 'ciencia-aberta-ubatuba' if ciencia-aberta-ubatuba.html became /ciencia-aberta-ubatuba/index.md)
KNOWN_CONTENT_ROOT_SLUGS = ['blog', 'video', 'consulta', 'contents']

# --- Helper Functions ---

def slugify_path_segment(text_segment):
    """Creates a basic slug from a single path segment for directory/file naming an comparisons."""
    if text_segment is None: return "default-slug"
    s = str(text_segment).lower()
    s = unidecode(s)
    s = re.sub(r'\s+', '-', s)      # Replace spaces with hyphens
    s = re.sub(r'[^\w\-]', '', s)   # Keep only word chars, digits, hyphens
    s = re.sub(r'\-{2,}', '-', s)   # Replace multiple hyphens with a single one
    s = s.strip('-')                # Remove leading/trailing hyphens
    if not s: return "untitled-segment" # Avoid empty segment
    return s

def is_segment_correctly_slugified(text_segment):
    """Checks if a single path segment is ALREADY correctly slugified (strict)."""
    if not text_segment: return True
    is_correct = (
        text_segment == text_segment.lower() and
        ' ' not in text_segment and
        '_' not in text_segment and
        text_segment == unidecode(text_segment) and
        not re.search(r"[^a-z0-9\-]", text_segment)
    )
    return is_correct

def check_path_segments_slugified(path_str): # For checking permalinks
    parts_to_check = [segment for segment in Path(path_str).parts if segment and segment != '/']
    return all(is_segment_correctly_slugified(segment) for segment in parts_to_check)

def generate_expected_jekyll_permalink(file_path_obj_relative_to_repo_root, known_content_roots, base_repo_root_obj):
    """
    Generates an expected Jekyll permalink based on the file's path relative to the repo root.
    Assumes that the file_path_obj_relative_to_repo_root is like 'blog/YYYY/MM/slugified_dir_name/index.md' or 'pagename_slug/index.md'.
    The permalink is based on the directory structure containing the index.md file.
    """
    try:
        # Path of the directory containing index.md, relative to the repo root
        # e.g., blog/2024/01/my-post (if file is blog/2024/01/my-post/index.md)
        # e.g., my-page (if file is my-page/index.md)
        containing_dir_path_relative_to_repo = file_path_obj_relative_to_repo_root.parent

        slugified_parts = []
        for part in containing_dir_path_relative_to_repo.parts:
            slugified_parts.append(slugify_path_segment(part))

        # Handle cases where containing_dir_path_relative_to_repo might be '.' (Path('.').parts is ('.',))
        # or if slugified_parts becomes empty due to slugifying '.'
        final_parts = [p for p in slugified_parts if p and p != 'default-slug' and p != '.']
        if not final_parts: # This happens if the file is like 'some-slug/index.md' directly in base_repo_root_obj
            return f"/{slugify_path_segment(file_path_obj_relative_to_repo_root.parent.name)}/"

        return f"/{'/'.join(final_parts)}/"

    except Exception as e:
        print(f"    Error generating expected permalink for {file_path_obj_relative_to_repo_root}: {e}")
        # Fallback based on the directory containing index.md, slugified
        return f"/{slugify_path_segment(file_path_obj_relative_to_repo_root.parent.name)}/"


def audit_markdown_file(file_path_obj, base_dir_path_obj, known_content_roots_for_permalinks):
    issues_found_for_file = []
    repo_root_path = base_dir_path_obj # In this script, base_dir is the repo root
    try:
        with open(file_path_obj, 'r', encoding='utf-8') as f: content = f.read()

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                front_matter_str = parts[1]; markdown_body = parts[2]
                try: fm = yaml.safe_load(front_matter_str)
                except yaml.YAMLError as e: issues_found_for_file.append(f"  YAML Error: {e}"); fm = None

                if fm:
                    if 'permalink' in fm:
                        permalink = fm['permalink']
                        if not permalink.startswith('/'): issues_found_for_file.append(f"  Permalink Style: '{permalink}' should start with '/'.")
                        if not permalink.endswith('/'): issues_found_for_file.append(f"  Permalink Style: '{permalink}' should end with '/'.")
                        if not check_path_segments_slugified(permalink):
                            issues_found_for_file.append(f"  Permalink Slug: '{permalink}' has non-slugified segments (check case, accents, spaces, underscores). Expected similar to: '{generate_expected_jekyll_permalink(file_path_obj.relative_to(repo_root_path), known_content_roots_for_permalinks, repo_root_path)}'")

                        expected_permalink = generate_expected_jekyll_permalink(file_path_obj.relative_to(repo_root_path), known_content_roots_for_permalinks, repo_root_path)
                        if permalink != expected_permalink:
                             issues_found_for_file.append(f"  Permalink vs Path: For file '{file_path_obj.relative_to(repo_root_path)}', permalink is '{permalink}', but path implies: '{expected_permalink}'")
                    else: issues_found_for_file.append("  Front Matter: Missing 'permalink' field.")
                else: issues_found_for_file.append("  Front Matter: Could not be parsed.")

                internal_links = re.findall(r'\\[.*?\\]\((?!http)(?!mailto:)(?!tel:)([^)]+)\)', markdown_body)
                for link_href in internal_links:
                    href_to_check = unquote(link_href.split('#')[0].split('?')[0])
                    if href_to_check.endswith(".html"): issues_found_for_file.append(f"  Content Link: Points to '.html': [{link_href}]")

                    path_obj = Path(href_to_check)
                    if not path_obj.is_absolute() or (str(path_obj).startswith('/') and not str(path_obj).startswith('//')):
                        # Check segments of relative or root-relative paths
                        for i, segment in enumerate(path_obj.parts):
                            # For root-relative, first segment is '/', ignore. For relative, no leading '/' in parts.
                            if (str(path_obj).startswith('/') and i == 0 and segment == '/') or segment in ['.', '..']:
                                continue
                            if segment and not is_segment_correctly_slugified(segment):
                                issues_found_for_file.append(f"  Content Link: Segment '{segment}' in '[{link_href}]' may not be slugified (expected similar to '{slugify_path_segment(segment)}')")
                                break
            else: issues_found_for_file.append("  Content: Could not parse front matter (no closing '---').")
        else: issues_found_for_file.append("  Content: No YAML front matter found.")

    except Exception as e: issues_found_for_file.append(f"  Processing Error for {file_path_obj.name}: {e}")
    return issues_found_for_file

if __name__ == "__main__":
    base_dir = Path(CONTENT_BASE_DIR).resolve()
    print(f"Starting audit in directory: {base_dir}")
    print(f"Auditing content based on these configured root items (expecting them as subdirectories or slugified page-directories in '{base_dir}'): {KNOWN_CONTENT_ROOT_SLUGS}")
    print("---")

    total_issues = 0; files_audited = 0

    for content_root_slug_str_from_config in KNOWN_CONTENT_ROOT_SLUGS:
        item_path = base_dir / content_root_slug_str_from_config

        if item_path.is_dir():
            if not is_segment_correctly_slugified(item_path.name):
                print(f"[DIRECTORY WARNING] Top-level content directory name not slugified: '{item_path.name}' (expected: '{slugify_path_segment(item_path.name)}')")
                total_issues +=1

            for root_str, dirs_in_walk, files_in_walk in os.walk(item_path):
                current_dir_path = Path(root_str)
                if current_dir_path != item_path:
                    path_to_check_segments = current_dir_path.relative_to(item_path)
                    for part in path_to_check_segments.parts:
                        if part and not is_segment_correctly_slugified(part):
                            print(f"[DIRECTORY WARNING] Subdirectory segment '{part}' in '{current_dir_path.relative_to(base_dir)}' not slugified (expected: '{slugify_path_segment(part)}')")
                            total_issues += 1
                            break

                for filename in files_in_walk:
                    if filename == "index.md":
                        file_path_obj = current_dir_path / filename
                        relative_display_path = file_path_obj.relative_to(base_dir) if base_dir != Path('.') else file_path_obj
                        print(f"Auditing: {relative_display_path}")
                        files_audited += 1
                        issues = audit_markdown_file(file_path_obj, base_dir, KNOWN_CONTENT_ROOT_SLUGS)
                        if issues:
                            for issue in issues: print(issue); total_issues += len(issues)
                        else: print("  No issues found.")
        else:
            print(f"[CONFIG WARNING] Configured content item '{content_root_slug_str_from_config}' (path: '{item_path}') is not a directory. Please check `KNOWN_CONTENT_ROOT_SLUGS` and your generated file structure. If it's a page like 'about.md' it should be in a directory like 'about/index.md' for this audit script version.")

    print("\n--- Audit Complete ---")
    print(f"Files Audited: {files_audited}")
    print(f"Total Potential Issues Found: {total_issues}")
    if total_issues > 0: print("\nPlease review the warnings above. This script does not modify any files.")
    else: print("Looks good from this basic audit!")
