#!/usr/bin/env bash
set -euo pipefail

echo "=== Video Editor.app installer ==="

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

on autoImportResolve(timelinePath)
    do shell script "/usr/bin/open -a 'DaVinci Resolve'"
    delay 4
    tell application "DaVinci Resolve" to activate
    delay 1
    set the clipboard to timelinePath
    tell application "System Events"
        -- Resolve 21: File > Import Timeline uses Shift-Command-I.
        keystroke "i" using {shift down, command down}
        delay 1
        -- macOS file chooser: jump directly to the exact FCPXML path.
        keystroke "g" using {shift down, command down}
        delay 0.5
        keystroke "v" using {command down}
        delay 0.3
        key code 36
        delay 0.8
        key code 36
        delay 2
        -- Accept Resolve's Load XML dialog with its current/default settings.
        key code 36
    end tell
end autoImportResolve

on processVideo(inputPath)
    set projectDir to "${PROJECT_DIR}"
    set editorBin to projectDir & "/.venv/bin/video-editor"
    set outputDir to projectDir & "/output"

    set baseName to do shell script "/usr/bin/basename " & quoted form of inputPath
    set stemName to do shell script "/bin/echo " & quoted form of baseName & " | /usr/bin/sed -E 's/[.][^.]+$//'"
    set outputPath to outputDir & "/" & stemName & "_rough.mp4"
    set timelinePath to outputDir & "/" & stemName & "_rough.fcpxml"

    set shellCmd to "export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin; " & ¬
        "/bin/mkdir -p " & quoted form of outputDir & "; " & ¬
        quoted form of editorBin & " process " & quoted form of inputPath & " -o " & quoted form of outputPath & ¬
        " --resolve --resolve-output " & quoted form of timelinePath

    try
        with timeout of 3600 seconds
            do shell script shellCmd
        end timeout
        display notification "Rough cut + Resolve timeline ready" with title "Video Editor"
        set resultDialog to display dialog "Done. Rough cut and DaVinci timeline are ready." buttons {"Show Files", "Open DaVinci", "Auto Import"} default button "Auto Import" with icon note
        set pickedButton to button returned of resultDialog
        if pickedButton is "Auto Import" then
            my autoImportResolve(timelinePath)
        else if pickedButton is "Open DaVinci" then
            do shell script "/usr/bin/open -a 'DaVinci Resolve'"
            delay 2
            do shell script "/usr/bin/open -R " & quoted form of timelinePath
        else
            do shell script "/usr/bin/open -R " & quoted form of outputPath
        end if
    on error errMsg number errNum
        display dialog "Video Editor error:" & return & errMsg buttons {"OK"} default button "OK" with icon stop
    end try
end processVideo
EOF

rm -rf "$APP_PATH"
osacompile -o "$APP_PATH" "$TMP_SCRIPT"
rm -f "$TMP_SCRIPT"

echo "Installed: $APP_PATH"
echo "Open it from Spotlight or ~/Applications."
echo "You can also drag a video directly onto the app icon."
echo "Each run creates *_rough.mp4 + *_rough.fcpxml."
echo "Auto Import is experimental and needs macOS Accessibility permission for Video Editor.app."
