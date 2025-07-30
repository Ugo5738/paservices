#!/bin/bash
# Master script to run daily data capture and analysis tasks >

# Exit immediately if any command fails
set -e

# --- Configuration ---
# URLs for services within the Docker network
export AUTH_SERVICE_URL="http://auth_service:8000"
export SUPER_ID_SERVICE_URL="http://super_id_service:8000"
export DATA_CAPTURE_RIGHTMOVE_SERVICE_URL="http://data_capture_rightmove_service:8000"

# --- IMPORTANT: REPLACE THESE PLACEHOLDER VALUES ---
LOCATION="REGION^503"  # Example: London region. Use the one >
API_PHONE="2347033588401"       # The phone number for the ex>
API_PASSWORD="password" # The password for the external API a>
# ----------------------------------------------------

# --- Script Setup ---
# Ensure we are running from the project's root directory on >
cd /home/ubuntu/paservices

LOG_FILE="/home/ubuntu/paservices/daily_tasks.log"

# Function to monitor logs for a completion message
# Usage: monitor_logs "Completion Message" "Task Name" TIMEOUT_SECONDS
monitor_logs() {
    local success_message="$1"
    local task_name="$2"
    local timeout="$3"
    local start_time=$(date +%s)

    echo "--> Monitoring logs for completion of '$task_name'..." | tee -a $LOG_FILE
    echo "    (Looking for message: '$success_message')" | tee -a $LOG_FILE

    while true; do
        # Check logs from the last 5 minutes for the success message
        if docker compose -f docker-compose.prod.yml logs --since 5m data_capture_rightmove_service | grep -q "$success_message"; then
            echo "--> '$task_name' completed successfully." | tee -a $LOG_FILE
            return 0
        fi
    
        local current_time=$(date +%s)
        local elapsed=$(($current_time - $start_time))

        if [ $elapsed -ge $timeout ]; then
            echo "--> ERROR: Timed out after $timeout seconds waiting for '$task_name' to complete." | tee -a $LOG_FILE
            return 1
        fi

        echo "    ($elapsed/$timeout s) Waiting for '$task_name' to finish..."
        sleep 30 # Wait for 30 seconds before checking again
    done
}

# === Main Execution ===
    
echo "==================================================" >> $LOG_FILE
echo "Starting daily tasks at $(date)" >> $LOG_FILE
echo "==================================================" >> $LOG_FILE

# --- Step 1: Search for new properties ---
echo "Step 1: Initiating property search..." | tee -a $LOG_FILE
docker compose -f docker-compose.prod.yml run --rm data_capture_rightmove_service python scripts/search_properties.py --identifier "$LOCATION_IDENTIFIER" --num-properties 10000 --sort-by "NewestListed" >> $LOG_FILE 2>&1

# Wait for the search to complete (timeout of 2 hours)
monitor_logs "Search for ${LOCATION_IDENTIFIER} complete" "Property Search" 7200

# --- Step 2: Scrape details for recently found properties ---
echo "Step 2: Initiating detailed scrape for today's properties..." | tee -a $LOG_FILE
docker compose -f docker-compose.prod.yml run --rm data_capture_rightmove_service python scripts/scrape_details.py --date "$(date +'%Y-%m-%d')" >> $LOG_FILE 2>&1

# Wait for scraping to complete (timeout of 3 hours)
monitor_logs "Detailed Scrape Workflow Complete" "Detailed Scrape" 10800

# --- Step 3: Trigger analysis for the scraped properties ---
echo "Step 3: Initiating external analysis..." | tee -a $LOG_FILE
docker compose -f docker-compose.prod.yml run --rm data_capture_rightmove_service python scripts/trigger_analysis.py --api-phone "$EXTERNAL_API_PHONE" --api-password "$EXTERNAL_API_PASSWORD" --date "$(date +'%Y-%m-%d')" >> $LOG_FILE 2>&1

# Wait for analysis to complete (timeout of 3 hours)
monitor_logs "External Analysis Trigger Workflow Complete" "External Analysis" 10800

echo "==================================================" >> $LOG_FILE
echo "All daily tasks finished at $(date)" >> $LOG_FILE
echo "==================================================" >> $LOG_FILE