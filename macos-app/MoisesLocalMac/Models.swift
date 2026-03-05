import Foundation

struct JobStatus: Codable {
    let id: String
    let status: String
    let progress: Double
    let message: String
    let output_dir: String
    let stems_dir: String
    let preset: String
    let error: String?
}

struct SeparateRequest: Codable {
    let input_path: String
    let output_dir: String
    let stems: Int
    let preset: String
}

enum Preset: String, CaseIterable, Identifiable {
    case fast = "fast"
    case best = "best"
    case vocalBoost = "vocal_boost"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .fast: return "Fast"
        case .best: return "Best Quality"
        case .vocalBoost: return "Vocal Boost (hook)"
        }
    }
}
