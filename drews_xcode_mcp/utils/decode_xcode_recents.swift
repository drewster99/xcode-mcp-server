#!/usr/bin/swift
import Foundation

/// Decode Xcode recent documents from macOS shared file list
/// Reads bookmark data and outputs paths to .xcodeproj and .xcworkspace files
/// Usage: swift decode_xcode_recents.swift

let plistPath = NSString(string: "~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/com.apple.dt.xcode.sfl3").expandingTildeInPath

guard FileManager.default.fileExists(atPath: plistPath) else {
    // Silently exit if file doesn't exist - no recent items
    exit(0)
}

guard let plistData = try? Data(contentsOf: URL(fileURLWithPath: plistPath)),
      let plist = try? PropertyListSerialization.propertyList(from: plistData, format: nil) as? [String: Any],
      let objects = plist["$objects"] as? [Any] else {
    // Failed to parse - exit silently
    exit(0)
}

var paths: [String] = []

for obj in objects {
    if let bookmarkData = obj as? Data {
        do {
            var isStale = false
            let url = try URL(resolvingBookmarkData: bookmarkData, bookmarkDataIsStale: &isStale)
            let path = url.path

            // Only include .xcodeproj and .xcworkspace files
            if path.hasSuffix(".xcodeproj") || path.hasSuffix(".xcworkspace") {
                // Skip if file no longer exists
                if FileManager.default.fileExists(atPath: path) {
                    paths.append(path)
                }
            }
        } catch {
            // Not a valid bookmark or file doesn't exist, skip
        }
    }
}

// Output paths one per line
for path in paths {
    print(path)
}
