#!/usr/bin/env swift
/// Reads a UserInterfaceState.xcuserstate file (NSKeyedArchiver binary plist)
/// and extracts the last-used run destination identifier for each scheme.
///
/// Output: JSON object mapping scheme names to destination identifiers.
/// Example: {"MyApp": "03A7716E-4962-4F2D-9455-E27C81883D4D_iphonesimulator_arm64"}
///
/// Usage: swift decode_active_destination.swift <path-to-xcuserstate>

import Foundation

guard CommandLine.arguments.count > 1 else {
    fputs("Usage: decode_active_destination.swift <path-to-xcuserstate>\n", stderr)
    exit(1)
}

let filePath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: filePath)

guard let data = try? Data(contentsOf: url) else {
    fputs("Error: Cannot read file: \(filePath)\n", stderr)
    exit(1)
}

guard let plist = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any],
      let objects = plist["$objects"] as? [Any] else {
    fputs("Error: Cannot parse plist\n", stderr)
    exit(1)
}

/// Extract the integer value from a CFKeyedArchiverUID object via its description.
/// These are opaque types that can't be cast directly, but their description
/// has the format: "<CFKeyedArchiverUID ...>{value = N}"
func uidValue(_ obj: Any) -> Int? {
    let desc = "\(obj)"
    guard desc.contains("CFKeyedArchiverUID"),
          let range = desc.range(of: "value = "),
          let endRange = desc[range.upperBound...].range(of: "}") else {
        return nil
    }
    return Int(desc[range.upperBound..<endRange.lowerBound])
}

// Find the index of the destination key in the $objects array
var targetKeyIndex: Int?
for (i, obj) in objects.enumerated() {
    if let s = obj as? String, s == "IDERunContextRecentsLastUsedRunDestinationBySchemeKey" {
        targetKeyIndex = i
        break
    }
}

guard let keyIndex = targetKeyIndex else {
    // No destination data — project may never have been run
    print("{}")
    exit(0)
}

// Walk the $objects array to find the NSDictionary that references this key,
// then extract the scheme-to-destination mapping from its corresponding value
for obj in objects {
    guard let dict = obj as? [String: Any],
          let nsKeys = dict["NS.keys"] as? [Any],
          let nsObjects = dict["NS.objects"] as? [Any],
          nsKeys.count == nsObjects.count else { continue }

    for (ki, key) in nsKeys.enumerated() {
        guard let uid = uidValue(key), uid == keyIndex else { continue }

        // Resolve the value: a dict mapping scheme names to destination strings
        guard let valueUid = uidValue(nsObjects[ki]),
              valueUid < objects.count,
              let schemeDict = objects[valueUid] as? [String: Any],
              let schemeKeys = schemeDict["NS.keys"] as? [Any],
              let schemeValues = schemeDict["NS.objects"] as? [Any],
              schemeKeys.count == schemeValues.count else { continue }

        var result: [String: String] = [:]
        for (si, sk) in schemeKeys.enumerated() {
            guard let skUid = uidValue(sk), skUid < objects.count,
                  let schemeName = objects[skUid] as? String else { continue }

            guard let svUid = uidValue(schemeValues[si]), svUid < objects.count else { continue }
            let destObj = objects[svUid]

            if let destStr = destObj as? String {
                result[schemeName] = destStr
            } else if let destDict = destObj as? [String: Any],
                      let nsString = destDict["NS.string"] as? String {
                result[schemeName] = nsString
            }
        }

        if let jsonData = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        } else {
            print("{}")
        }
        exit(0)
    }
}

print("{}")
