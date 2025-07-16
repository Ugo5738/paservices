import os
import sys

# Define sets for faster lookups
EXCLUDED_FILENAMES = {".DS_Store", "poetry.lock"}
EXCLUDED_EXTENSIONS = {".log"}
# Directories whose *contents* (and subdirectories) should be entirely excluded if their name appears anywhere in the path
EXCLUDED_DIR_COMPONENTS = {
    "migrations",
    "staticfiles",
    "__pycache__",
    ".cursor",
    "vendor",
    ".pytest_cache" ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "app",
    "keys",
    "k8s",
    "sql",
    "docs",
}
# Directory names to prune from os.walk (won't descend into them)
PRUNE_DIRS = {
    "migrations",
    "staticfiles",
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
}


def should_exclude(file_path):
    basename = os.path.basename(file_path)
    if basename in EXCLUDED_FILENAMES:
        return True

    if file_path.lower().endswith(
        tuple(EXCLUDED_EXTENSIONS)
    ):  # endswith can take a tuple
        return True

    path_components = set(file_path.split(os.sep))
    if not EXCLUDED_DIR_COMPONENTS.isdisjoint(path_components):
        return True
    # Add more exclusion rules here if necessary
    return False


def _write_file_to_outfile(file_path, outfile, header_path_display):
    """Helper function to write a single file's content to the outfile."""
    if should_exclude(file_path):
        print(f"Excluding: {file_path}")
        return

    # Normalize the header path for display
    normalized_header_path = os.path.normpath(header_path_display)
    outfile.write(f"# {normalized_header_path}\n")
    print(f"Adding: {normalized_header_path}")

    try:
        with open(
            file_path, "r", encoding="utf-8", errors="ignore"
        ) as infile:  # Added errors='ignore' for robustness
            outfile.write(infile.read())
    except Exception as e:
        outfile.write(f"// Error reading file {file_path}: {e}\n")
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)

    # Separate file sections by extra newlines
    outfile.write("\n\n")


def merge_code(input_paths, output_file="merged_code.txt"):
    with open(output_file, "w", encoding="utf-8") as outfile:
        for path_arg in input_paths:
            if os.path.isdir(path_arg):
                # This is a directory, walk through it
                # The base_dir for relpath calculation is the directory_arg itself
                base_dir_for_relpath = path_arg
                for root, dirs, files in os.walk(path_arg, topdown=True):
                    # Prune excluded directories from further traversal
                    dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]

                    for file in files:
                        file_path = os.path.join(root, file)
                        # The header should show the original directory argument + relative path
                        relative_file_path = os.path.relpath(
                            file_path, base_dir_for_relpath
                        )
                        header_display = os.path.join(
                            base_dir_for_relpath, relative_file_path
                        )
                        _write_file_to_outfile(file_path, outfile, header_display)

            elif os.path.isfile(path_arg):
                # This is a single file
                # The header is just the file path argument itself
                _write_file_to_outfile(path_arg, outfile, path_arg)
            else:
                print(
                    f"Warning: '{path_arg}' is not a valid file or directory. Skipping.",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge_code.py <output_file> <path1> [path2 ...]")
        print("  <pathN> can be a file or a directory.")
        sys.exit(1)  # Exit with an error code

    output_file_arg = sys.argv[1]
    paths_to_process = sys.argv[2:]
    merge_code(paths_to_process, output_file_arg)
    print(f"\nSuccessfully merged code into {output_file_arg}")
