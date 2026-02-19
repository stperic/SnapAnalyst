#!/bin/bash
# SnapAnalyst - Download SNAP QC Data from USDA FNS
# 
# This script downloads the SNAP Quality Control public use files from
# the USDA Food and Nutrition Service website.
#
# Data Source: https://www.fns.usda.gov/snap/quality-control-data
#
# Usage:
#   ./scripts/download_data.sh              # Download all available years
#   ./scripts/download_data.sh 2023         # Download specific year
#   ./scripts/download_data.sh --docker     # Download for Docker (uses /data path)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Default data directory (can be overridden for Docker)
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/datasets/snap/data}"

# SNAP QC Data URLs (loaded from config.yaml)
# Note: These URLs may change. Update datasets/snap/config.yaml when they do.
# Data Source: https://snapqcdata.net/data

CONFIG_FILE="$PROJECT_ROOT/datasets/snap/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Parse data_files from config.yaml using Python (requires PyYAML: pip install pyyaml)
if ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${RED}Error: PyYAML is required. Install with: pip install pyyaml${NC}"
    exit 1
fi

declare -A DATA_URLS
while IFS='=' read -r year url; do
    DATA_URLS["$year"]="$url"
done < <(python3 -c "
import yaml, sys
with open('$CONFIG_FILE') as f:
    config = yaml.safe_load(f)
for year, url in config.get('data_files', {}).items():
    print(f'{year}={url}')
")

if [ ${#DATA_URLS[@]} -eq 0 ]; then
    echo -e "${RED}Error: No data_files found in $CONFIG_FILE${NC}"
    exit 1
fi

# Note: Each ZIP file is approximately 200-300MB and contains CSV files

# Parse arguments
DOCKER_MODE=false
SPECIFIC_YEAR=""

for arg in "$@"; do
    case $arg in
        --docker)
            DOCKER_MODE=true
            DATA_DIR="/data"
            shift
            ;;
        20[0-9][0-9])
            SPECIFIC_YEAR="$arg"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [YEAR]"
            echo ""
            echo "Download SNAP QC data from USDA FNS."
            echo ""
            echo "Options:"
            echo "  --docker    Use Docker data path (/data)"
            echo "  --help      Show this help message"
            echo ""
            echo "Arguments:"
            echo "  YEAR        Specific fiscal year to download (e.g., 2023)"
            echo "              If not specified, downloads all available years."
            echo ""
            echo "Available years: ${!DATA_URLS[*]}"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SNAP QC Data Downloader${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"
echo -e "${YELLOW}Data directory:${NC} $DATA_DIR"
echo ""

# Function to download and extract a file
download_file() {
    local year=$1
    local url=${DATA_URLS[$year]}
    local zip_filename="qcfy${year}_csv.zip"
    local zip_path="${DATA_DIR}/${zip_filename}"
    
    echo -e "${YELLOW}Downloading FY${year} data...${NC}"
    echo -e "  URL: ${url}"
    echo -e "  Destination: ${DATA_DIR}"
    
    # Check if CSV file already exists (skip download)
    if ls "${DATA_DIR}"/qc_pub_fy${year}*.csv 1> /dev/null 2>&1; then
        echo -e "  ${GREEN}CSV file for FY${year} already exists. Skipping...${NC}"
        echo -e "  (Delete CSV files and re-run to re-download)"
        return 0
    fi
    
    # Download ZIP file using curl with progress bar
    # Note: snapqcdata.net requires a User-Agent header
    echo -e "  ${YELLOW}Downloading ZIP file...${NC}"
    if curl -L -A "Mozilla/5.0" --progress-bar -o "$zip_path" "$url"; then
        # Verify file was downloaded (check size)
        local filesize=$(stat -f%z "$zip_path" 2>/dev/null || stat -c%s "$zip_path" 2>/dev/null)
        if [ "$filesize" -lt 1000 ]; then
            echo -e "  ${RED}Error: Downloaded file is too small (${filesize} bytes).${NC}"
            echo -e "  ${RED}The URL may have changed. Please check:${NC}"
            echo -e "  ${RED}https://snapqcdata.net/data${NC}"
            rm -f "$zip_path"
            return 1
        fi
        echo -e "  ${GREEN}Downloaded successfully ($(numfmt --to=iec-i --suffix=B $filesize 2>/dev/null || echo "${filesize} bytes"))${NC}"
    else
        echo -e "  ${RED}Error: Download failed.${NC}"
        echo -e "  ${RED}Please check your internet connection and try again.${NC}"
        rm -f "$zip_path"
        return 1
    fi
    
    # Extract ZIP file
    echo -e "  ${YELLOW}Extracting ZIP file...${NC}"
    if command -v unzip &> /dev/null; then
        if unzip -q "$zip_path" -d "$DATA_DIR"; then
            echo -e "  ${GREEN}Extraction completed successfully${NC}"
            # Clean up ZIP file
            rm -f "$zip_path"
            echo -e "  ${YELLOW}Removed ZIP file to save space${NC}"
        else
            echo -e "  ${RED}Error: Extraction failed.${NC}"
            rm -f "$zip_path"
            return 1
        fi
    else
        echo -e "  ${RED}Error: unzip command not found. Please install unzip.${NC}"
        return 1
    fi
    
    echo ""
}

# Download files
DOWNLOAD_COUNT=0
FAILED_COUNT=0

if [ -n "$SPECIFIC_YEAR" ]; then
    # Download specific year
    if [ -z "${DATA_URLS[$SPECIFIC_YEAR]}" ]; then
        echo -e "${RED}Error: Year $SPECIFIC_YEAR is not available.${NC}"
        echo -e "Available years: ${!DATA_URLS[*]}"
        exit 1
    fi
    if download_file "$SPECIFIC_YEAR"; then
        ((DOWNLOAD_COUNT++))
    else
        ((FAILED_COUNT++))
    fi
else
    # Download all available years
    echo -e "${YELLOW}Downloading all available fiscal years...${NC}"
    echo ""
    for year in "${!DATA_URLS[@]}"; do
        if download_file "$year"; then
            ((DOWNLOAD_COUNT++))
        else
            ((FAILED_COUNT++))
        fi
    done
fi

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Download Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ $FAILED_COUNT -eq 0 ]; then
    echo -e "${GREEN}All downloads completed successfully!${NC}"
else
    echo -e "${YELLOW}Downloads completed with errors.${NC}"
    echo -e "  Successful: ${DOWNLOAD_COUNT}"
    echo -e "  Failed: ${FAILED_COUNT}"
fi

echo ""
echo -e "${YELLOW}Data files location:${NC} $DATA_DIR"
echo ""

# List downloaded files
echo -e "${YELLOW}Available data files:${NC}"
ls -lh "$DATA_DIR"/*.csv 2>/dev/null || echo "  No CSV files found."
echo ""

# Next steps
echo -e "${BLUE}Next Steps:${NC}"
if [ "$DOCKER_MODE" = true ]; then
    echo -e "  1. Start the application: docker-compose up"
    echo -e "  2. Load data in UI: /load qc_pub_fy2023"
else
    echo -e "  1. Start the application: ./start_all.sh"
    echo -e "  2. Open the UI: http://localhost:8001"
    echo -e "  3. Load data: /load qc_pub_fy2023"
fi
