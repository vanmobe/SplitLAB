import SwiftUI
import AppKit

struct LibraryView: View {
    @ObservedObject var store = LibraryStore.shared

    var body: some View {
        VStack(alignment: .leading) {
            Text("Library").font(.headline)
            List(store.items) { item in
                HStack {
                    VStack(alignment: .leading) {
                        Text(item.fileName).bold()
                        Text(item.preset).font(.caption).foregroundStyle(.secondary)
                        Text(item.createdAt.formatted()).font(.caption2).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Open") {
                        NSWorkspace.shared.open(URL(fileURLWithPath: item.stemsDir))
                    }
                }
            }
        }
    }
}
