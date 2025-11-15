#!/bin/bash

# Script to restore original file timestamps from iCloud Drive to local files
# This preserves the original creation and modification dates

ICLOUD_DOCS="/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Documents"
ICLOUD_DOWNLOADS="/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Downloads"
LOCAL_DOCS="/Users/kendall/Documents"
LOCAL_DOWNLOADS="/Users/kendall/Downloads"

echo "🕐 Restoring original file timestamps..."
echo ""
echo "⚠️  This will update file modification times from iCloud Drive originals"
echo ""

# Function to restore timestamps for a directory
restore_timestamps() {
    local source_dir=$1
    local dest_dir=$2
    local name=$3
    
    if [ ! -d "$source_dir" ]; then
        echo "   ⚠️  Source directory not found: $source_dir"
        return
    fi
    
    echo "📁 Processing $name files..."
    local count=0
    
    # Find all files in source and restore their timestamps in destination
    find "$source_dir" -type f -print0 | while IFS= read -r -d '' source_file; do
        # Get relative path from source directory
        rel_path="${source_file#$source_dir/}"
        dest_file="$dest_dir/$rel_path"
        
        if [ -f "$dest_file" ]; then
            # Copy timestamps from source to destination
            # -m: modification time, -t: use reference file's time
            touch -r "$source_file" "$dest_file" 2>/dev/null
            if [ $? -eq 0 ]; then
                count=$((count + 1))
                if [ $((count % 50)) -eq 0 ]; then
                    echo "   Processed $count files..."
                fi
            fi
        fi
    done
    
    echo "   ✅ Restored timestamps for files in $name"
}

# Restore Documents timestamps
echo "📄 Restoring Documents timestamps..."
restore_timestamps "$ICLOUD_DOCS" "$LOCAL_DOCS" "Documents"

# Restore Downloads timestamps  
echo "📥 Restoring Downloads timestamps..."
restore_timestamps "$ICLOUD_DOWNLOADS" "$LOCAL_DOWNLOADS" "Downloads"

echo ""
echo "✨ Timestamp restoration complete!"
echo ""
echo "📋 Note:"
echo "   - Modification times have been restored"
echo "   - Creation times on macOS are harder to preserve, but modification times"
echo "     should help maintain chronological order"
echo "   - You can verify by checking file properties"

