#!/bin/bash
# Create real Xcode projects using xcodebuild

set -e

echo "Creating valid Xcode test projects..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$REPO_ROOT"

# Clean templates directory
rm -rf test_projects/templates
mkdir -p test_projects/templates

echo ""
echo "=== Creating test projects ==="

# Create SimpleApp as a basic Swift package project
cd "$REPO_ROOT/test_projects/templates"
mkdir -p SimpleApp
cd SimpleApp

# Create a minimal but valid xcodeproj using plutil
mkdir -p SimpleApp.xcodeproj
cat > SimpleApp.xcodeproj/project.pbxproj << 'PBXPROJ'
// !$*UTF8*$!
{
	archiveVersion = 1;
	classes = {
	};
	objectVersion = 56;
	objects = {

/* Begin PBXBuildFile section */
		8D11052D0486CEB800E47090 /* main.swift in Sources */ = {isa = PBXBuildFile; fileRef = 08FB7796FE84155DC02AAC07 /* main.swift */; };
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
		08FB7796FE84155DC02AAC07 /* main.swift */ = {isa = PBXFileReference; fileEncoding = 4; lastKnownFileType = sourcecode.swift; path = main.swift; sourceTree = "<group>"; };
		8D1107320486CEB800E47090 /* SimpleApp */ = {isa = PBXFileReference; explicitFileType = "compiled.mach-o.executable"; includeInIndex = 0; path = SimpleApp; sourceTree = BUILT_PRODUCTS_DIR; };
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		8D11052C0486CEB800E47090 /* Frameworks */ = {
			isa = PBXFrameworksBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
		08FB7794FE84155DC02AAC07 /* SimpleApp */ = {
			isa = PBXGroup;
			children = (
				08FB7796FE84155DC02AAC07 /* main.swift */,
				1AB674ADFE9D54B511CA2CBB /* Products */,
			);
			name = SimpleApp;
			sourceTree = "<group>";
		};
		1AB674ADFE9D54B511CA2CBB /* Products */ = {
			isa = PBXGroup;
			children = (
				8D1107320486CEB800E47090 /* SimpleApp */,
			);
			name = Products;
			sourceTree = "<group>";
		};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		8D1107260486CEB800E47090 /* SimpleApp */ = {
			isa = PBXNativeTarget;
			buildConfigurationList = 1DEB923108733DC60010E9CD /* Build configuration list for PBXNativeTarget "SimpleApp" */;
			buildPhases = (
				8D11052C0486CEB800E47090 /* Frameworks */,
				8D11052D0486CEB800E47090 /* Sources */,
			);
			buildRules = (
			);
			dependencies = (
			);
			name = SimpleApp;
			productName = SimpleApp;
			productReference = 8D1107320486CEB800E47090 /* SimpleApp */;
			productType = "com.apple.product-type.tool";
		};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		08FB7793FE84155DC02AAC07 /* Project object */ = {
			isa = PBXProject;
			attributes = {
				LastSwiftUpdateCheck = 1500;
				LastUpgradeCheck = 1500;
			};
			buildConfigurationList = 1DEB923508733DC60010E9CD /* Build configuration list for PBXProject "SimpleApp" */;
			compatibilityVersion = "Xcode 14.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
			);
			mainGroup = 08FB7794FE84155DC02AAC07 /* SimpleApp */;
			projectDirPath = "";
			projectRoot = "";
			targets = (
				8D1107260486CEB800E47090 /* SimpleApp */,
			);
		};
/* End PBXProject section */

/* Begin PBXSourcesBuildPhase section */
		8D11052D0486CEB800E47090 /* Sources */ = {
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				8D11052D0486CEB800E47090 /* main.swift in Sources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		1DEB923208733DC60010E9CD /* Debug */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				PRODUCT_NAME = SimpleApp;
				SWIFT_VERSION = 5.0;
			};
			name = Debug;
		};
		1DEB923308733DC60010E9CD /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				PRODUCT_NAME = SimpleApp;
				SWIFT_VERSION = 5.0;
			};
			name = Release;
		};
		1DEB923608733DC60010E9CD /* Debug */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				SDKROOT = macosx;
				SWIFT_VERSION = 5.0;
			};
			name = Debug;
		};
		1DEB923708733DC60010E9CD /* Release */ = {
			isa = XCBuildConfiguration;
			buildSettings = {
				SDKROOT = macosx;
				SWIFT_VERSION = 5.0;
			};
			name = Release;
		};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		1DEB923108733DC60010E9CD /* Build configuration list for PBXNativeTarget "SimpleApp" */ = {
			isa = XCConfigurationList;
			buildConfigurations = (
				1DEB923208733DC60010E9CD /* Debug */,
				1DEB923308733DC60010E9CD /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
		1DEB923508733DC60010E9CD /* Build configuration list for PBXProject "SimpleApp" */ = {
			isa = XCConfigurationList;
			buildConfigurations = (
				1DEB923608733DC60010E9CD /* Debug */,
				1DEB923708733DC60010E9CD /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		};
/* End XCConfigurationList section */
	};
	rootObject = 08FB7793FE84155DC02AAC07 /* Project object */;
}
PBXPROJ

# Create main.swift
cat > main.swift << 'EOF'
import Foundation

print("Hello from SimpleApp!")
print("Current time: \(Date())")

for i in 1...5 {
    print("Count: \(i)")
}

print("SimpleApp completed successfully")
EOF

echo "✅ Created SimpleApp"

# Copy SimpleApp as base for other projects
cd "$REPO_ROOT/test_projects/templates"
cp -r SimpleApp BrokenApp
cp -r SimpleApp ConsoleApp

# Modify BrokenApp
cd BrokenApp
mv SimpleApp.xcodeproj BrokenApp.xcodeproj
sed -i '' 's/SimpleApp/BrokenApp/g' BrokenApp.xcodeproj/project.pbxproj

cat > main.swift << 'EOF'
import Foundation

// This will cause an error - undefined variable
print(undefinedVariable)

// This will cause a warning - unused variable
let unusedVariable = "This is never used"

print("This won't compile")
EOF

echo "✅ Created BrokenApp"

# Modify ConsoleApp
cd "$REPO_ROOT/test_projects/templates/ConsoleApp"
mv SimpleApp.xcodeproj ConsoleApp.xcodeproj
sed -i '' 's/SimpleApp/ConsoleApp/g' ConsoleApp.xcodeproj/project.pbxproj

cat > main.swift << 'EOF'
import Foundation

print("=== ConsoleApp Started ===")
print("[INFO] Application initialized")
print("[WARNING] This is a warning")

for i in 1...10 {
    print("Line \(i): Output")
}

print("TEST_MARKER: Special output")
print("=== ConsoleApp Completed ===")
EOF

echo "✅ Created ConsoleApp"

echo ""
echo "✅ All test projects created successfully!"