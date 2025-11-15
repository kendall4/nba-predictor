# iCloud Drive Migration Guide

## ✅ Current Status

### Already Migrated (Correct Location)
- ✅ **Project**: `~/Documents/projects/nba-predictor` - Already in correct location
- ✅ **Downloads**: `~/Downloads` - Has files locally

### Still in iCloud Drive (Need Migration)

#### Documents Folder (`~/Library/Mobile Documents/com~apple~CloudDocs/Documents/`)
Contains:
- School work (comp 2210, engl 2260, etc.)
- PDFs (lease documents, resumes, etc.)
- Music files
- Adobe/Image-Line/VirtualDJ application data
- Various documents and projects

#### Downloads Folder (`~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/`)
Contains:
- PDFs (lease documents, lab reports, etc.)
- Images (jpg, gif files)
- Application installers
- Various downloaded files

## 🚀 Migration Options

### Option 1: Use the Migration Script (Recommended)

I've created a script at: `migrate_from_icloud.sh`

**To run it:**
```bash
cd ~/Documents/projects/nba-predictor
bash migrate_from_icloud.sh
```

**What it does:**
1. Removes empty nested folders (`~/Documents/Documents/` and `~/Documents/Downloads/`)
2. Moves files from iCloud Documents to `~/Documents/`
3. Moves files from iCloud Downloads to `~/Downloads/`
4. Cleans up empty iCloud folders

### Option 2: Manual Migration

#### Step 1: Clean Up Empty Folders
```bash
rm -rf ~/Documents/Documents
rm -rf ~/Documents/Downloads
```

#### Step 2: Move Documents
```bash
# Move files from iCloud Documents (excluding nested folders)
cd "/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Documents"
# Move individual files/folders to ~/Documents/
# Skip "Documents - Mac - 1" folder (already migrated)
```

#### Step 3: Move Downloads
```bash
# Move all files from iCloud Downloads
rsync -av "/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Downloads/" ~/Downloads/
```

#### Step 4: Verify and Clean Up
After verifying files are in correct locations:
```bash
# Remove empty iCloud folders
rm -rf "/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents - Mac - 1"
```

## ⚠️ Important Notes

1. **Backup First**: Consider backing up important files before migration
2. **Check for Duplicates**: Some files might already exist locally - the script handles this
3. **Application Data**: Some folders like `Adobe/`, `Image-Line/`, `VirtualDJ/` contain application settings - you may want to keep these in iCloud or move them carefully
4. **Verify After Migration**: Check that all files are accessible after migration

## 📋 Files to Review Before Migration

### Application Data (Consider keeping in iCloud or moving carefully):
- `Adobe/` - Adobe application settings
- `Image-Line/` - FL Studio settings
- `VirtualDJ/` - VirtualDJ settings and playlists

### School Work (Should be moved):
- `comp 2210/` - Computer science coursework
- `engl 2260 mcteague analysis.docx` - English assignments
- Various PDF assignments and lab reports

### Personal Documents (Should be moved):
- Resume PDFs
- Lease documents
- Music files

## 🎯 Quick Commands

**Check what's in iCloud Documents:**
```bash
ls -la "/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Documents/"
```

**Check what's in iCloud Downloads:**
```bash
ls -la "/Users/kendall/Library/Mobile Documents/com~apple~CloudDocs/Downloads/"
```

**Check local Documents:**
```bash
ls -la ~/Documents/
```

**Check local Downloads:**
```bash
ls -la ~/Downloads/
```

