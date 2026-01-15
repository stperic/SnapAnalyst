# CSV Upload Feature

## Overview
Added functionality to allow users to upload CSV files directly from the browser to the SnapAnalyst application.

## Changes Made

### 1. Backend API Changes (`src/api/routers/files.py`)

Added a new `/upload` endpoint that:
- Accepts CSV file uploads via multipart/form-data
- Validates file type (only .csv files)
- Sanitizes filenames to prevent directory traversal
- Handles duplicate filenames by adding timestamps
- Saves files to the `snapdata/` directory
- Extracts fiscal year from filename
- Returns file metadata

**Endpoint:** `POST /api/v1/data/upload`

**Request:**
```
Content-Type: multipart/form-data
file: [CSV file]
```

**Response:**
```json
{
  "status": "success",
  "message": "File uploaded successfully: filename.csv",
  "file": {
    "filename": "filename.csv",
    "fiscal_year": 2023,
    "size_mb": 1.5,
    "size_bytes": 1572864,
    "last_modified": "2026-01-14T18:36:00",
    "loaded": false,
    "loaded_at": null,
    "row_count": null
  }
}
```

### 2. Frontend Changes (`chainlit_app.py`)

Added `/upload` command that:
- Prompts user to select a CSV file from their computer
- Shows upload progress
- Uploads file to the API
- Displays success message with file details
- Provides a quick action button to load the file immediately

**Usage:**
```
/upload
```

**Features:**
- Accept only CSV files
- Maximum file size: 100 MB
- 180 second timeout for upload
- Auto-detection of fiscal year from filename
- Action button to immediately load uploaded file

### 3. Help Documentation Updates

Updated help message to include:
```
**Data Loading:**
- `/files` - List available CSV files
- `/load <filename>` - Load a specific CSV file
- `/upload` - Upload a CSV file from your computer
```

Updated welcome message to mention upload capability.

## User Workflow

1. User types `/upload` in the chat
2. Chainlit displays file picker dialog
3. User selects CSV file from their computer
4. File is uploaded to the server
5. File is saved to `snapdata/` directory
6. User receives confirmation with file details
7. User can click "Load Now" button to immediately load the file, or use `/load filename` later

## Benefits

- **Convenience**: No need to manually copy files to the server
- **User-friendly**: Simple browser-based upload interface
- **Safe**: Filename sanitization prevents security issues
- **Integrated**: Seamlessly integrates with existing load workflow
- **Flexible**: Supports any CSV file format

## Technical Details

### File Validation
- Only `.csv` extensions accepted
- Maximum size: 100 MB
- Files saved with sanitized names
- Duplicate detection with automatic timestamp suffixing

### Fiscal Year Detection
Automatically detects fiscal year from filename patterns:
- `fy2023`, `FY2023` → 2023
- `fy23`, `FY23` → 2023  
- `2023` → 2023

### Error Handling
- Invalid file types rejected
- Upload timeouts handled gracefully
- API errors displayed to user with details
- Network issues shown with helpful messages

## Testing

To test the upload feature:

1. Start the application: `./start_all.sh`
2. Open http://localhost:8001
3. Type `/upload` in the chat
4. Select a CSV file
5. Verify file uploads successfully
6. Use `/files` to see the uploaded file
7. Use `/load filename` to load it into the database

## Future Enhancements

Possible improvements:
- Progress bar for large file uploads
- File validation before upload (check CSV structure)
- Batch upload (multiple files at once)
- Auto-load option after upload
- File preview before uploading
- Drag-and-drop upload interface
