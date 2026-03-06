import Foundation

@MainActor
final class EngineManager: ObservableObject {
    static let shared = EngineManager()
    private init() {}

    @Published var isRunning: Bool = false
    @Published var statusMessage: String = "Engine not started"

    private var process: Process?

    private let port: Int = 8732

    func ensureRunning(engineDirHint: URL?) async {
        if await pingHealth() {
            isRunning = true
            statusMessage = "Engine running"
            return
        }

        guard let engineDir = resolveEngineDir(hint: engineDirHint) else {
            isRunning = false
            statusMessage = "Engine folder not found. Expected a local 'engine/' directory."
            return
        }

        guard start(engineDir: engineDir) else {
            isRunning = false
            return
        }

        for _ in 0..<20 {
            try? await Task.sleep(nanoseconds: 200_000_000)
            if await pingHealth() {
                isRunning = true
                statusMessage = "Engine running"
                return
            }
        }
        isRunning = false
        statusMessage = "Engine did not respond on http://127.0.0.1:\(port)"
    }

    private func start(engineDir: URL) -> Bool {
        guard let pythonURL = resolvePythonExecutable(engineDir: engineDir) else {
            statusMessage = "Python not found at engine/.venv/bin/python. Set up the engine venv first."
            return false
        }

        let p = Process()
        p.executableURL = pythonURL
        p.currentDirectoryURL = engineDir
        p.arguments = ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "\(port)"]

        let outPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = outPipe

        do {
            try p.run()
            process = p
            statusMessage = "Starting engine..."
            return true
        } catch {
            statusMessage = "Failed to start engine: \(error.localizedDescription)"
            return false
        }
    }

    private func pingHealth() async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)/health") else { return false }
        do {
            let (_, resp) = try await URLSession.shared.data(from: url)
            guard let http = resp as? HTTPURLResponse else { return false }
            return (200..<300).contains(http.statusCode)
        } catch {
            return false
        }
    }

    private func resolvePythonExecutable(engineDir: URL) -> URL? {
        let venvPython = engineDir.appendingPathComponent(".venv/bin/python")
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            return venvPython
        }

        let fallbackPaths = [
            "/opt/homebrew/bin/python3.13",
            "/usr/local/bin/python3.13",
            "/usr/bin/python3",
        ]
        for path in fallbackPaths where FileManager.default.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        return nil
    }

    private func resolveEngineDir(hint: URL?) -> URL? {
        var candidates: [URL] = []
        if let hint {
            candidates.append(hint)
        }

        let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        candidates.append(cwd.appendingPathComponent("engine", isDirectory: true))
        candidates.append(cwd.deletingLastPathComponent().appendingPathComponent("engine", isDirectory: true))

        for candidate in candidates {
            var isDir: ObjCBool = false
            if FileManager.default.fileExists(atPath: candidate.path, isDirectory: &isDir), isDir.boolValue {
                return candidate
            }
        }
        return nil
    }
}
