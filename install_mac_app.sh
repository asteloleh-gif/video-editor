#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Applications"
APP_PATH="$APP_DIR/Video Editor.app"
TMP_SCRIPT="$(mktemp -t video-editor-app).applescript"

if [ ! -x "$PROJECT_DIR/.venv/bin/video-editor" ]; then
  echo "video-editor is not installed in .venv. Run setup_mac.sh first."
  exit 1
fi

mkdir -p "$APP_DIR" "$PROJECT_DIR/output"

cat > "$TMP_SCRIPT" <<EOF
on run
    set pickedFile to choose file with prompt "Choose a RAW video"
    my processVideo(POSIX path of pickedFile)
end run

on open droppedItems
    repeat with anItem in droppedItems
        my processVideo(POSIX path of anItem)
    end repeat
end open

on processVideo(inputPath)
    set projectDir to "${PROJECT_DIR}"
    set editorBin to projectDir & "/.venv/bin/video-editor"
    set outputDir to projectDir & "/output"

    set baseName to do shell script "/usr/bin/basename " & quoted form of inputPath
    set stemName to do shell script "/bin/echo " & quoted form of baseName & " | /usr/bin/sed -E 's/\\.[^.]+$//'"
    set outputPath to outputDir & "/" & stemName & "_rough.mp4"

    set shellCmd to "export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin; " & ¬
        "/bin/mkdir -p " & quoted form of outputDir & "; " & ¬
        quoted form of editorBin & " process " & quoted form of inputPath & " -o " & quoted form of outputPath

    try
        with timeout of 3600 seconds
            do shell script shellCmd
        end timeout
        display notification "Rough cut ready" with title "Video Editor"
        do shell script "/usr/bin/open -R " & quoted form of outputPath
    on error errMsg number errNum
        display dialog "Video Editor error:" & return & errMsg buttons {"OK"} default button "OK" with icon stop
    end try
end processVideo
EOF

rm -rf "$APP_PATH"
osacompile -o "$APP_PATH" "$TMP_SCRIPT"
rm -f "$TMP_SCRIPT"

echo "Installed: $APP_PATH"
echo "Open it from Finder > Applications, Spotlight, or drag it to the Dock."
echo "You can also drag a video directly onto the app icon."
