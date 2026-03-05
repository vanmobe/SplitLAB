import Foundation

@MainActor
final class EngineManager: ObservableObject {
    static let shared = EngineManager()
    private init() {}

    @Published var isRunning: Bool = false
    private var process: Process?

    private let pythonPath = "/usr/bin/python3"
    private let port: Int = 8732

    func ensureRunning(engineDir: URL) async {
        if await pingHealth() {
            isRunning = true
            return
        }
        start(engineDir: engineDir)
        for _ in 0..<20 {
            try? await Task.sleep(nanoseconds: 200_000_000)
            if await pingHealth() {
                isRunning = true
                return
            }
        }
        isRunning = false
    }

    private func start(engineDir: URL) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: pythonPath)
        p.currentDirectoryURL = engineDir
        p.arguments = ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "\(port)"]

        let outPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = outPipe

        do {
            try p.run()
            process = p
        } catch {
            print("Failed to start engine:", error)
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
}
