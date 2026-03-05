import SwiftUI
import AppKit

struct ContentView: View {
    @State private var pickedFile: URL?
    @State private var outputFolder: URL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Music")
        .appendingPathComponent("MoisesLocalOutput")

    @State private var stems: Int = 4
    @State private var preset: Preset = .best

    @State private var job: JobStatus?
    @State private var isRunning = false
    @State private var errorText: String?

    @StateObject private var engine = EngineManager.shared

    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 12) {
                Text("Moises Local (Mac)").font(.title2).bold()

                HStack {
                    Button("Choose Audio…") { pickAudio() }
                    if let pickedFile {
                        Text(pickedFile.lastPathComponent).lineLimit(1)
                    } else {
                        Text("No file selected").foregroundStyle(.secondary)
                    }
                }

                HStack {
                    Text("Preset:")
                    Picker("", selection: $preset) {
                        ForEach(Preset.allCases) { p in
                            Text(p.title).tag(p)
                        }
                    }
                    .frame(maxWidth: 260)
                }

                HStack {
                    Text("Stems:")
                    Picker("", selection: $stems) {
                        Text("2 (vocals + instrumental)").tag(2)
                        Text("4 (vocals/drums/bass/other)").tag(4)
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 360)
                }

                HStack {
                    Button(isRunning ? "Running…" : "Split") {
                        Task { await startJob() }
                    }
                    .disabled(pickedFile == nil || isRunning || !engine.isRunning)

                    Button("Open Output Folder") {
                        NSWorkspace.shared.open(outputFolder)
                    }
                }

                Text(engine.isRunning ? "Engine: running" : "Engine: not running")
                    .font(.caption)
                    .foregroundStyle(engine.isRunning ? .secondary : .red)

                if let job {
                    ProgressView(value: job.progress)
                    Text("\(Int(job.progress * 100))% — \(job.status)")
                        .font(.caption)
                    Text(job.message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }

                if let errorText {
                    Text(errorText)
                        .foregroundStyle(.red)
                        .font(.caption)
                }

                Spacer()
            }
            .padding(16)
            .frame(width: 620, height: 360)
            .onDrop(of: ["public.file-url"], isTargeted: nil) { providers in
                if let item = providers.first {
                    _ = item.loadObject(ofClass: NSURL.self) { url, _ in
                        DispatchQueue.main.async { self.pickedFile = url as URL? }
                    }
                    return true
                }
                return false
            }
            .task {
                let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                    .appendingPathComponent("MoisesLocalMac", isDirectory: true)
                try? FileManager.default.createDirectory(at: appSupport, withIntermediateDirectories: true)
                LibraryStore.shared.open(at: appSupport.appendingPathComponent("library.sqlite"))

                // DEV path: assumes you run the app while current directory is repo root.
                // If not, replace with an absolute path to your repo's engine folder.
                let devEngineDir = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
                    .appendingPathComponent("engine", isDirectory: true)

                await engine.ensureRunning(engineDir: devEngineDir)
            }

            LibraryView()
                .frame(width: 420, height: 360)
                .padding(.trailing, 16)
        }
    }

    private func pickAudio() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.audio]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        if panel.runModal() == .OK {
            pickedFile = panel.url
        }
    }

    private func startJob() async {
        guard let pickedFile else { return }
        errorText = nil
        isRunning = true

        do {
            let initial = try await EngineClient.shared.separate(
                inputPath: pickedFile.path,
                outputDir: outputFolder.path,
                stems: stems,
                preset: preset
            )
            job = initial

            while true {
                try await Task.sleep(nanoseconds: 600_000_000)
                let updated = try await EngineClient.shared.job(jobID: initial.id)
                job = updated

                if updated.status == "done" {
                    isRunning = false
                    LibraryStore.shared.add(job: updated, inputPath: pickedFile.path)
                    NSWorkspace.shared.open(URL(fileURLWithPath: updated.stems_dir))
                    break
                }
                if updated.status == "error" {
                    isRunning = false
                    errorText = updated.error ?? "Unknown error"
                    break
                }
            }
        } catch {
            isRunning = false
            errorText = error.localizedDescription
        }
    }
}
