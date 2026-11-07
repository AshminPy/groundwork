import AppKit
import AVFoundation
import SwiftUI

@main
struct ArchitectCoachApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        Settings { SettingsView(coach: delegate.coach) }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let coach = Coach()
    private var window: NSWindow?
    private var hotkey: Hotkey?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 720),
                              styleMask: [.titled, .closable, .resizable, .miniaturizable],
                              backing: .buffered, defer: false)
        window.title = "Architect Coach"
        window.contentView = NSHostingView(rootView: MainView(coach: coach))
        window.center()
        window.makeKeyAndOrderFront(nil)
        self.window = window
        // ⌃⌥Space: stop the coach talking and take the floor.
        hotkey = Hotkey { [weak self] in self?.coach.interrupt() }
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

struct MainView: View {
    @ObservedObject var coach: Coach
    @State private var typed = ""

    var body: some View {
        VStack(spacing: 10) {
            header
            conversation
            if coach.inSession { controls }
            HStack {
                TextField("Type instead of talking…", text: $typed)
                    .onSubmit {
                        let text = typed.trimmingCharacters(in: .whitespaces)
                        guard !text.isEmpty else { return }
                        typed = ""
                        coach.send(text, spoken: coach.inSession)
                    }
            }
            Text(coach.status).font(.caption2).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled)
        }
        .padding(14)
        .frame(minWidth: 440, minHeight: 560)
    }

    private var header: some View {
        HStack(spacing: 12) {
            Orb(phase: coach.phase, muted: coach.muted)
            VStack(alignment: .leading) {
                Text(coach.coachName).font(.headline)
                Text(coach.muted && coach.inSession ? "Muted" : coach.phase.rawValue)
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Picker("", selection: $coach.mode) {
                ForEach(CoachMode.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.menu).frame(width: 130)
            Button(coach.inSession ? "End" : "Start talking") {
                if coach.inSession { coach.endSession() } else { Task { await coach.startSession() } }
            }
            .keyboardShortcut("l", modifiers: [.command])
        }
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    if coach.turns.isEmpty {
                        Text("Press Start talking, then just speak. Pause to hand over. Try: “I need to decide how our services connect to CloudAMQP. Coach me.”")
                            .foregroundStyle(.secondary).padding(.top, 20)
                    }
                    ForEach(coach.turns) { turn in Bubble(turn: turn, coachName: coach.coachName) }
                    if !coach.partial.isEmpty {
                        Text(coach.partial).italic().foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    Color.clear.frame(height: 1).id("end")
                }
            }
            .onChange(of: coach.turns.last?.text) { proxy.scrollTo("end") }
            .onChange(of: coach.partial) { proxy.scrollTo("end") }
        }
    }

    private var controls: some View {
        HStack {
            Button(coach.muted ? "Unmute" : "Mute") { coach.toggleMute() }
            Button("Interrupt (⌃⌥Space)") { coach.interrupt() }
                .disabled(coach.phase != .speaking && coach.phase != .thinking)
            Button(coach.screenshotNext ? "Screen: next turn ✓" : "Show my screen") { coach.screenshotNext.toggle() }
                .help("Attach one screenshot to your next message (diagram, console, ticket).")
            Spacer()
            Menu("More") {
                Button("Write decision record (ADR)") { coach.writeDecisionRecord() }
                Button("New topic") { coach.newTopic() }
                Button("Open notes folder") { NSWorkspace.shared.open(Storage.root) }
            }
            .frame(width: 80)
        }
        .font(.callout)
    }
}

struct Orb: View {
    let phase: Phase
    let muted: Bool
    @State private var pulse = false

    var color: Color {
        if muted && phase != .idle { return .gray }
        switch phase {
        case .idle: return .gray
        case .listening: return .green
        case .thinking: return .orange
        case .speaking: return .blue
        }
    }

    var body: some View {
        Circle().fill(color.gradient)
            .frame(width: 34, height: 34)
            .scaleEffect(pulse && phase != .idle ? 1.12 : 1)
            .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: pulse)
            .onAppear { pulse = true }
    }
}

struct Bubble: View {
    let turn: Turn
    let coachName: String

    var body: some View {
        VStack(alignment: turn.fromUser ? .trailing : .leading, spacing: 4) {
            Text(turn.fromUser ? "You\(turn.hadScreenshot ? " · screenshot" : "")" : coachName)
                .font(.caption2).foregroundStyle(.secondary)
            Text(LocalizedStringKey(turn.text.isEmpty ? "…" : turn.text))
                .textSelection(.enabled)
                .padding(10)
                .background(turn.fromUser ? Color.accentColor.opacity(0.15) : Color.secondary.opacity(0.12),
                            in: RoundedRectangle(cornerRadius: 10))
            ForEach(Array(turn.sources.prefix(5).enumerated()), id: \.offset) { _, source in
                if let url = URL(string: source.url) {
                    Link(source.title, destination: url).font(.caption).lineLimit(1)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: turn.fromUser ? .trailing : .leading)
    }
}

struct SettingsView: View {
    @ObservedObject var coach: Coach
    @State private var apiKey = Keychain.load() ?? ""
    @State private var saved = false
    private let voices = Speaker.voices()

    var body: some View {
        Form {
            Section("Anthropic API key (stored in Keychain)") {
                SecureField("sk-ant-…", text: $apiKey)
                Button(saved ? "Saved" : "Save key") {
                    Keychain.save(apiKey.trimmingCharacters(in: .whitespacesAndNewlines))
                    saved = true
                }
            }
            Section("Coach") {
                TextField("Name", text: $coach.coachName)
                TextField("Model ID", text: $coach.model)
                Picker("Effort", selection: $coach.effort) {
                    ForEach(["low", "medium", "high"], id: \.self) { Text($0) }
                }
                Text("low = quick back-and-forth. medium/high = deeper design work, slower replies.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Voice") {
                Picker("Voice", selection: $coach.voiceID) {
                    Text("Best available").tag("")
                    ForEach(voices, id: \.identifier) { v in
                        Text("\(v.name) (\(v.language), \(v.quality == .premium ? "premium" : v.quality == .enhanced ? "enhanced" : "default"))")
                            .tag(v.identifier)
                    }
                }
                Slider(value: $coach.rate, in: Double(AVSpeechUtteranceMinimumSpeechRate)...Double(AVSpeechUtteranceMaximumSpeechRate)) {
                    Text("Speed")
                }
                Text("For a natural voice, download a Premium voice: System Settings > Accessibility > Spoken Content > System voice > Manage Voices.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Documentation search (empty = off)") {
                TextField("Allowed domains, comma-separated", text: $coach.domains, axis: .vertical)
                Text("Team knowledge: put .md/.txt files (ADRs, standards, ticket notes) in ~/Documents/ArchitectCoach/knowledge/. Loaded when a session starts.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding()
        .frame(width: 540)
    }
}
