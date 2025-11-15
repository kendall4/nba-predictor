#!/bin/bash

# Script to remove nested duplicate folders
# This removes nested Downloads, Documents, Desktop folders that shouldn't exist

echo "🧹 Cleaning up nested duplicate folders..."
echo ""

# Remove nested Downloads folder
if [ -d "/Users/kendall/Downloads/Downloads" ]; then
    echo "📁 Removing ~/Downloads/Downloads/ (nested duplicate)..."
    rm -rf "/Users/kendall/Downloads/Downloads"
    echo "   ✅ Removed"
else
    echo "   ℹ️  No nested Downloads folder found"
fi

# Remove nested Desktop folder in Documents (it's empty)
if [ -d "/Users/kendall/Documents/Desktop" ]; then
    echo "📁 Removing empty ~/Documents/Desktop/ folder..."
    rm -rf "/Users/kendall/Documents/Desktop"
    echo "   ✅ Removed"
else
    echo "   ℹ️  No nested Desktop folder found"
fi

# Move file from Documents - Mac to main Documents, then remove folder
if [ -d "/Users/kendall/Documents/Documents - Mac" ]; then
    echo "📁 Found ~/Documents/Documents - Mac/ folder"
    if [ -f "/Users/kendall/Documents/Documents - Mac/paystubes.pdf" ]; then
        echo "   Moving paystubes.pdf to main Documents folder..."
        mv "/Users/kendall/Documents/Documents - Mac/paystubes.pdf" "/Users/kendall/Documents/"
        echo "   ✅ Moved paystubes.pdf"
    fi
    echo "   Removing empty Documents - Mac folder..."
    rm -rf "/Users/kendall/Documents/Documents - Mac"
    echo "   ✅ Removed"
fi

echo ""
echo "✨ Cleanup complete!"
echo ""
echo "📋 Summary:"
echo "   ✅ Removed nested Downloads folder"
echo "   ✅ Removed nested Desktop folder"
echo "   ✅ Moved paystubes.pdf and removed Documents - Mac folder"

