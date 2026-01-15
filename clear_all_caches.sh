#!/bin/bash
set -e

echo "=========================================="
echo "Comprehensive Cache Clearing Script"
echo "=========================================="

# 1. Clear project Python caches
echo "1. Clearing project Python caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true

# 2. Clear Chainlit global Python caches
echo "2. Clearing Chainlit global Python caches..."
find /Users/eric/.local/share/python-tools/lib/python3.13/site-packages/chainlit -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 3. Touch files to update modification time (force cache bust)
echo "3. Updating file timestamps..."
touch public/logo_dark.png
touch public/logo_light.png  
touch public/custom.css
touch public/custom.js
touch .chainlit/config.toml

# 4. Verify file sizes
echo "4. Verifying files..."
python3 << 'EOF'
from PIL import Image
import os

logo_dark = 'public/logo_dark.png'
logo_light = 'public/logo_light.png'

img_dark = Image.open(logo_dark)
img_light = Image.open(logo_light)

print(f"✓ {logo_dark}: {img_dark.size} ({os.path.getsize(logo_dark)} bytes)")
print(f"✓ {logo_light}: {img_light.size} ({os.path.getsize(logo_light)} bytes)")

if img_dark.size == (241, 270) and img_light.size == (241, 270):
    print("✓ Logo dimensions are correct (241x270)")
else:
    print("✗ ERROR: Logo dimensions are incorrect!")
    exit(1)
EOF

echo "=========================================="
echo "Cache clearing complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Stop Chainlit if it's running"
echo "2. Run: ./start_chainlit.sh (or chainlit run chainlit_app.py)"
echo "3. Hard refresh your browser: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)"
echo ""

