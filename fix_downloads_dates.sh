#!/bin/bash

# Script to restore Downloads timestamps specifically
# This handles the Downloads folder separately to debug any issues

ICLOUD_DOWNLOADS="/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
LOCAL_DOWNLOADS="/Users/kendall/Downloads"

echo "🕐 Restoring Downloads file timestamps..."
echo ""

if [ ! -d "$ICLOUD_DOWNLOADS" ]; then
    echo "⚠️  iCloud Downloads folder not found!"
    echo "   Path: $ICLOUD_DOWNLOADS"
    exit 1
fi

if [ ! -d "$LOCAL_DOWNLOADS" ]; then
    echo "⚠️  Local Downloads folder not found!"
    echo "   Path: $LOCAL_DOWNLOADS"
    exit 1
fi

echo "📁 Source: $ICLOUD_DOWNLOADS"
echo "📁 Destination: $LOCAL_DOWNLOADS"
echo ""

count=0
matched=0
not_found=0

# Process files in iCloud Downloads
find "$ICLOUD_DOWNLOADS" -type f -print0 | while IFS= read -r -d '' source_file; do
    # Get just the filename (not full path)
    filename=$(basename "$source_file")
    dest_file="$LOCAL_DOWNLOADS/$filename"
    
    if [ -f "$dest_file" ]; then
        # Copy modification time from source to destination
        touch -r "$source_file" "$dest_file" 2>/dev/null
        if [ $? -eq 0 ]; then
            matched=$((matched + 1))
            if [ $((matched % 20)) -eq 0 ]; then
                echo "   Processed $matched files..."
            fi
        fi
    else
        not_found=$((not_found + 1))
        if [ $not_found -le 5 ]; then
            echo "   ⚠️  Not found locally: $filename"
        fi
    fi
    count=$((count + 1))
done

echo ""
echo "✨ Downloads timestamp restoration complete!"
echo "   Total files checked: $count"
echo "   Timestamps restored: $matched"
echo "   Not found locally: $not_found"
echo ""
echo "📋 Note:"
echo "   - Files that were downloaded recently will have recent dates (this is normal)"
echo "   - Only files that existed in iCloud Downloads before migration had dates restored"
echo "   - If you downloaded files today, they'll show today's date"

