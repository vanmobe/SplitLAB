import Foundation
import SQLite3

struct LibraryItem: Identifiable {
    let id: String
    let fileName: String
    let inputPath: String
    let stemsDir: String
    let preset: String
    let createdAt: Date
}

@MainActor
final class LibraryStore: ObservableObject {
    static let shared = LibraryStore()
    private init() {}

    @Published private(set) var items: [LibraryItem] = []

    private var db: OpaquePointer?

    func open(at url: URL) {
        let path = url.path
        if sqlite3_open(path, &db) != SQLITE_OK {
            print("Failed to open DB")
            return
        }

        let sql = """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            input_path TEXT NOT NULL,
            stems_dir TEXT NOT NULL,
            preset TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
        sqlite3_exec(db, sql, nil, nil, nil)
        reload()
    }

    func add(job: JobStatus, inputPath: String) {
        guard let db else { return }
        let fileName = URL(fileURLWithPath: inputPath).lastPathComponent
        let created = Date().timeIntervalSince1970

        let sql = "INSERT OR REPLACE INTO jobs (id, file_name, input_path, stems_dir, preset, created_at) VALUES (?, ?, ?, ?, ?, ?);"
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, sql, -1, &stmt, nil)

        sqlite3_bind_text(stmt, 1, (job.id as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 2, (fileName as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 3, (inputPath as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 4, (job.stems_dir as NSString).utf8String, -1, nil)
        sqlite3_bind_text(stmt, 5, (job.preset as NSString).utf8String, -1, nil)
        sqlite3_bind_double(stmt, 6, created)

        sqlite3_step(stmt)
        sqlite3_finalize(stmt)
        reload()
    }

    func reload() {
        guard let db else { return }
        var result: [LibraryItem] = []

        let sql = "SELECT id, file_name, input_path, stems_dir, preset, created_at FROM jobs ORDER BY created_at DESC;"
        var stmt: OpaquePointer?
        sqlite3_prepare_v2(db, sql, -1, &stmt, nil)

        while sqlite3_step(stmt) == SQLITE_ROW {
            let id = String(cString: sqlite3_column_text(stmt, 0))
            let fileName = String(cString: sqlite3_column_text(stmt, 1))
            let inputPath = String(cString: sqlite3_column_text(stmt, 2))
            let stemsDir = String(cString: sqlite3_column_text(stmt, 3))
            let preset = String(cString: sqlite3_column_text(stmt, 4))
            let createdAt = Date(timeIntervalSince1970: sqlite3_column_double(stmt, 5))

            result.append(LibraryItem(id: id, fileName: fileName, inputPath: inputPath, stemsDir: stemsDir, preset: preset, createdAt: createdAt))
        }
        sqlite3_finalize(stmt)

        items = result
    }
}
