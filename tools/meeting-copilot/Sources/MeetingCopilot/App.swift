import AppKit
import SwiftUI

@main
struct MeetingCopilotApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        Settings { SettingsView(copilot: delegate.copilot) }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let copilot = Copilot()
    private var panel: NSPanel?
    private var hotkey: Hotkey?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 440, height: 620),
                            styleMask: [.titled, .closable, .resizable, .utilityWindow],
                            backing: .buffered, defer: false)
        panel.title = "Meeting Copilot"
        panel.level = .floating
        panel.isFloatingPanel = true
        panel.hidesOnDeactivate = false
        // Deliberately NOT setting `sharingType = .none`: the window stays visible in screen shares.
        panel.contentView = NSHostingView(rootView: MainView(copilot: copilot))
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        self.panel = panel
        hotkey = Hotkey { [weak self] in self?.copilot.ask() }
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

struct MainView: View {
    @ObservedObject var copilot: Copilot
    @State private var custom = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button(copilot.isListening ? "Stop" : "Start listening") { copilot.toggleListening() }
                    .keyboardShortcut("l", modifiers: [.command])
                if copilot.isListening {
                    Label("Recording", systemImage: "record.circle.fill").foregroundStyle(.red)
                }
                Spacer()
                Button("Clear") { copilot.clear() }
            }
            Text("Tell everyone on the call that you are transcribing it.")
                .font(.caption).foregroundStyle(.secondary)

            GroupBox("Transcript") {
                ScrollViewReader { proxy in
                    ScrollView {
                        Text(copilot.transcriptText().isEmpty ? "…" : copilot.transcriptText())
                            .font(.callout).textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Color.clear.frame(height: 1).id("end")
                    }
                    .onChange(of: copilot.segments.count) { proxy.scrollTo("end") }
                }
                .frame(minHeight: 140)
            }

            HStack {
                Toggle("Include screen", isOn: $copilot.includeScreen)
                Toggle("Auto-answer questions", isOn: $copilot.autoAnswer)
            }.font(.caption)

            HStack {
                Button(copilot.isAnswering ? "Answering…" : "Answer (⌃⌥Space)") { copilot.ask() }
                    .keyboardShortcut(.return, modifiers: [.command])
                    .disabled(copilot.isAnswering)
                TextField("Or ask something specific…", text: $custom)
                    .onSubmit {
                        guard !custom.isEmpty else { return }
                        copilot.ask(instruction: custom)
                        custom = ""
                    }
            }

            GroupBox("Suggested answer") {
                ScrollView {
                    Text(copilot.answer.isEmpty ? "Press Answer when a question is asked." : copilot.answer)
                        .font(.body).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(minHeight: 160)
            }

            Text(copilot.status).font(.caption2).foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(minWidth: 380, minHeight: 520)
    }
}

struct SettingsView: View {
    @ObservedObject var copilot: Copilot
    @State private var apiKey = Keychain.load() ?? ""
    @State private var saved = false

    var body: some View {
        Form {
            Section("Anthropic API key (stored in Keychain)") {
                SecureField("sk-ant-…", text: $apiKey)
                Button(saved ? "Saved" : "Save key") {
                    Keychain.save(apiKey.trimmingCharacters(in: .whitespacesAndNewlines))
                    saved = true
                }
            }
            Section("Model") {
                TextField("Model ID", text: $copilot.model)
                Picker("Effort", selection: $copilot.effort) {
                    ForEach(["low", "medium", "high"], id: \.self) { Text($0) }
                }
                Text("Lower effort = faster answers. Use high for hard technical questions.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Your notes (agenda, your background, key facts)") {
                TextEditor(text: $copilot.notes).frame(minHeight: 180).font(.callout)
            }
        }
        .padding()
        .frame(width: 520)
    }
}
