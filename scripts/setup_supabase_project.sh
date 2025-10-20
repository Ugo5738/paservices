#!/bin/bash

# A script to initialize, link, and pull the schema for a Supabase project.
# It exits immediately if any command fails.
set -e

# --- USAGE ---
# ./setup_supabase_project.sh <directory_name> <supabase_project_ref>
# Example:
# ./setup_supabase_project.sh floorplan_service abcdefghijklmnopqrst

# 1. Check if the correct number of arguments were provided.
if [ "$#" -ne 2 ]; then
    echo "Error: Missing arguments."
    echo "Usage: $0 <directory_name> <supabase_project_ref>"
    exit 1
fi

# 2. Assign arguments to variables for clarity.
PROJECT_DIR=$1
PROJECT_REF=$2

echo "--- [START] Setting up Supabase for project: $PROJECT_DIR ---"

# 3. Navigate into the target project directory.
# The '|| exit' ensures the script stops if the directory doesn't exist.
cd "$PROJECT_DIR" || exit

# 4. Initialize a new Supabase project locally.
# The 'yes N' command automatically answers 'N' to the "Generate VS Code settings for Deno?" prompt.
# If you want to answer 'y', change it to 'yes y'.
echo "--> Initializing Supabase..."
yes y | npx supabase init

# 5. Link the local project to the remote Supabase project.
echo "--> Linking to project ref: $PROJECT_REF..."
npx supabase link --project-ref "$PROJECT_REF"

# 6. Pull the remote database schema into a local migration file.
echo "--> Pulling remote schema..."
npx supabase db pull

echo "--- [SUCCESS] Finished setting up $PROJECT_DIR ---"