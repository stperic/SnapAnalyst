#!/bin/bash
# SnapAnalyst Schema Export Script
# Exports all schema documentation in multiple formats

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   SnapAnalyst Schema Documentation Export  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
BASE_URL="http://localhost:8000/api/v1/schema"
OUTPUT_DIR="schema_exports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create output directory
echo -e "${YELLOW}📁 Creating output directory...${NC}"
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# Check if API is running
echo -e "${YELLOW}🔍 Checking API status...${NC}"
if ! curl -s "$BASE_URL/" > /dev/null 2>&1; then
    echo -e "${RED}❌ API is not running at $BASE_URL${NC}"
    echo "Please start the API with: ./start_all.sh"
    exit 1
fi
echo -e "${GREEN}✅ API is running${NC}"
echo ""

# Export CSV files
echo -e "${YELLOW}📊 Exporting CSV files...${NC}"
curl -s "${BASE_URL}/export/tables/csv" -o "tables.csv"
echo "  ✓ tables.csv"
curl -s "${BASE_URL}/export/code-lookups/csv" -o "code_lookups.csv"
echo "  ✓ code_lookups.csv"
curl -s "${BASE_URL}/export/relationships/csv" -o "relationships.csv"
echo "  ✓ relationships.csv"
echo ""

# Export PDF files
echo -e "${YELLOW}📄 Exporting PDF files...${NC}"
curl -s "${BASE_URL}/export/tables/pdf" -o "tables.pdf"
echo "  ✓ tables.pdf"
curl -s "${BASE_URL}/export/code-lookups/pdf" -o "code_lookups.pdf"
echo "  ✓ code_lookups.pdf"
curl -s "${BASE_URL}/export/database-info/pdf" -o "database_info.pdf"
echo "  ✓ database_info.pdf"
echo ""

# Export Markdown files
echo -e "${YELLOW}📝 Exporting Markdown files...${NC}"
curl -s "${BASE_URL}/export/tables/markdown" -o "tables.md"
echo "  ✓ tables.md"
curl -s "${BASE_URL}/export/code-lookups/markdown" -o "code_lookups.md"
echo "  ✓ code_lookups.md"
echo ""

# Create timestamped archive
echo -e "${YELLOW}📦 Creating archive...${NC}"
cd ..
tar -czf "schema_exports_${TIMESTAMP}.tar.gz" "$OUTPUT_DIR"
echo -e "${GREEN}✅ Archive created: schema_exports_${TIMESTAMP}.tar.gz${NC}"
echo ""

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Export Complete! ✨               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 Export Summary:${NC}"
echo "  Location: $(pwd)/$OUTPUT_DIR/"
echo ""
echo -e "${BLUE}📁 Files exported:${NC}"
ls -lh "$OUTPUT_DIR" | tail -n +2 | awk '{printf "  %-20s %8s\n", $9, $5}'
echo ""
echo -e "${BLUE}📦 Archive:${NC}"
ls -lh "schema_exports_${TIMESTAMP}.tar.gz" | awk '{printf "  %-40s %8s\n", $9, $5}'
echo ""
echo -e "${YELLOW}💡 Next steps:${NC}"
echo "  - View files: cd $OUTPUT_DIR && ls"
echo "  - Open CSV:   open $OUTPUT_DIR/tables.csv"
echo "  - Open PDF:   open $OUTPUT_DIR/tables.pdf"
echo "  - View Markdown: cat $OUTPUT_DIR/tables.md"
echo ""
echo -e "${GREEN}🎉 All schema documentation exported successfully!${NC}"
