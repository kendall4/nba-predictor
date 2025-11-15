#!/bin/bash

# Migration script to move files from iCloud Drive back to local directories
# Run this script from your terminal: bash migrate_from_icloud.sh

set -e  # Exit on error

ICLOUD_DOCS="/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Documents"
ICLOUD_DOWNLOADS="/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
LOCAL_DOCS="/Users/kendall/Documents"
LOCAL_DOWNLOADS="/Users/kendall/Downloads"

echo "🔄 Starting migration from iCloud Drive to local directories..."
echo ""

# Function to safely move files
move_files() {
    local source=$1
    local dest=$2
    local name=$3
    
    if [ -d "$source" ] && [ "$(ls -A $source 2>/dev/null)" ]; then
        echo "📁 Moving $name files..."
        echo "   From: $source"
        echo "   To: $dest"
        
        # Create destination if it doesn't exist
        mkdir -p "$dest"
        
        # Move files (rsync for safety, then remove source)
        rsync -av --progress "$source/" "$dest/" 2>/dev/null || {
            echo "   ⚠️  Some files may already exist - skipping duplicates"
        }
        
        echo "   ✅ Completed"
        echo ""
    else
        echo "   ℹ️  No files to move in $name"
        echo ""
    fi
}

# Step 1: Clean up empty nested folders
echo "🧹 Step 1: Cleaning up empty nested folders..."
if [ -d "$LOCAL_DOCS/Documents" ] && [ -z "$(ls -A $LOCAL_DOCS/Documents 2>/dev/null)" ]; then
    rm -rf "$LOCAL_DOCS/Documents"
    echo "   ✅ Removed empty ~/Documents/Documents/"
fi

if [ -d "$LOCAL_DOCS/Downloads" ] && [ -z "$(ls -A $LOCAL_DOCS/Downloads 2>/dev/null)" ]; then
    rm -rf "$LOCAL_DOCS/Downloads"
    echo "   ✅ Removed empty ~/Documents/Downloads/"
fi
echo ""

# Step 2: Move Documents files (excluding the nested structure)
echo "📄 Step 2: Moving Documents files..."
if [ -d "$ICLOUD_DOCS" ]; then
    # Move files directly in Documents, but skip "Documents - Mac - 1" folder
    for item in "$ICLOUD_DOCS"/*; do
        if [ -e "$item" ]; then
            filename=$(basename "$item")
            # Skip the nested "Documents - Mac - 1" folder (already migrated)
            if [ "$filename" != "Documents - Mac - 1" ]; then
                echo "   Moving: $filename"
                mv "$item" "$LOCAL_DOCS/" 2>/dev/null || {
                    echo "   ⚠️  $filename already exists locally - skipping"
                }
            fi
        fi
    done
    echo "   ✅ Documents migration completed"
else
    echo "   ℹ️  No iCloud Documents folder found"
fi
echo ""

# Step 3: Move Downloads files
echo "📥 Step 3: Moving Downloads files..."
move_files "$ICLOUD_DOWNLOADS" "$LOCAL_DOWNLOADS" "Downloads"

# Step 4: Clean up empty iCloud folders
echo "🧹 Step 4: Cleaning up empty iCloud folders..."
if [ -d "$ICLOUD_DOCS/Documents - Mac - 1/projects" ] && [ -z "$(ls -A "$ICLOUD_DOCS/Documents - Mac - 1/projects" 2>/dev/null)" ]; then
    rm -rf "$ICLOUD_DOCS/Documents - Mac - 1"
    echo "   ✅ Removed empty iCloud projects folder"
fi

echo ""
echo "✨ Migration complete!"
echo ""
echo "📋 Summary:"
echo "   - Documents: Check ~/Documents/"
echo "   - Downloads: Check ~/Downloads/"
echo ""
echo "⚠️  Note: Please verify your files are in the correct locations."
echo "   You can safely delete the iCloud Drive folders after verification."

