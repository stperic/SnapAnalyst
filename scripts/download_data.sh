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

# USDA FNS base URL for SNAP QC data
# Note: These URLs may change. Check https://www.fns.usda.gov/snap/quality-control-data for updates.
BASE_URL="https://www.fns.usda.gov/sites/default/files/resource-files"

# Available fiscal years and their file names
# These are the publicly available SNAP QC files from USDA FNS
declare -A DATA_FILES=(
    ["2023"]="qc_pub_fy2023.csv"
    ["2022"]="qc_pub_fy2022.csv"
    ["2021"]="qc_pub_fy2021.csv"
)

# Note: Each file is approximately 200-250MB

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
            echo "Available years: ${!DATA_FILES[*]}"
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

# Function to download a file
download_file() {
    local year=$1
    local filename=${DATA_FILES[$year]}
    local url="${BASE_URL}/${filename}"
    local output_path="${DATA_DIR}/${filename}"
    
    echo -e "${YELLOW}Downloading FY${year} data...${NC}"
    echo -e "  URL: ${url}"
    echo -e "  Destination: ${output_path}"
    
    # Check if file already exists
    if [ -f "$output_path" ]; then
        echo -e "  ${YELLOW}File already exists. Skipping...${NC}"
        echo -e "  (Delete the file and re-run to re-download)"
        return 0
    fi
    
    # Download using curl with progress bar
    if curl -L --progress-bar -o "$output_path" "$url"; then
        # Verify file was downloaded (check size)
        local filesize=$(stat -f%z "$output_path" 2>/dev/null || stat -c%s "$output_path" 2>/dev/null)
        if [ "$filesize" -lt 1000 ]; then
            echo -e "  ${RED}Error: Downloaded file is too small (${filesize} bytes).${NC}"
            echo -e "  ${RED}The URL may have changed. Please check:${NC}"
            echo -e "  ${RED}https://www.fns.usda.gov/snap/quality-control-data${NC}"
            rm -f "$output_path"
            return 1
        fi
        echo -e "  ${GREEN}Downloaded successfully ($(numfmt --to=iec-i --suffix=B $filesize 2>/dev/null || echo "${filesize} bytes"))${NC}"
    else
        echo -e "  ${RED}Error: Download failed.${NC}"
        echo -e "  ${RED}Please check your internet connection and try again.${NC}"
        rm -f "$output_path"
        return 1
    fi
    
    echo ""
}

# Download files
DOWNLOAD_COUNT=0
FAILED_COUNT=0

if [ -n "$SPECIFIC_YEAR" ]; then
    # Download specific year
    if [ -z "${DATA_FILES[$SPECIFIC_YEAR]}" ]; then
        echo -e "${RED}Error: Year $SPECIFIC_YEAR is not available.${NC}"
        echo -e "Available years: ${!DATA_FILES[*]}"
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
    for year in "${!DATA_FILES[@]}"; do
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
