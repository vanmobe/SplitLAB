import Foundation

final class EngineClient {
    static let shared = EngineClient()
    private init() {}

    private let baseURL = URL(string: "http://127.0.0.1:8732")!

    func separate(inputPath: String, outputDir: String, stems: Int, preset: Preset) async throws -> JobStatus {
        let url = baseURL.appendingPathComponent("separate")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = SeparateRequest(input_path: inputPath, output_dir: outputDir, stems: stems, preset: preset.rawValue)
        req.httpBody = try JSONEncoder().encode(body)

        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw NSError(domain: "EngineClient", code: 1, userInfo: [NSLocalizedDescriptionKey: "Engine error"])
        }
        return try JSONDecoder().decode(JobStatus.self, from: data)
    }

    func job(jobID: String) async throws -> JobStatus {
        let url = baseURL.appendingPathComponent("jobs/\(jobID)")
        let (data, resp) = try await URLSession.shared.data(from: url)
        guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw NSError(domain: "EngineClient", code: 2, userInfo: [NSLocalizedDescriptionKey: "Job fetch error"])
        }
        return try JSONDecoder().decode(JobStatus.self, from: data)
    }
}
