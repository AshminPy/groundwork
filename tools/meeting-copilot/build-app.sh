#!/usr/bin/env bash
# Build MeetingCopilot.app from the Swift package. Run on macOS 14+ with Xcode 15+ installed.
set -euo pipefail
cd "$(dirname "$0")"
swift build -c release
APP="build/MeetingCopilot.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$(swift build -c release --show-bin-path)/MeetingCopilot" "$APP/Contents/MacOS/"
cp Info.plist "$APP/Contents/Info.plist"
# Ad-hoc signature so macOS privacy permissions (TCC) attach to this bundle.
codesign --force --sign - "$APP"
echo "Built $APP"
echo "Run: open $APP"
