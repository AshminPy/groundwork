// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "ArchitectCoach",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "ArchitectCoach",
            path: "Sources/ArchitectCoach"
        )
    ]
)
