import SwiftUI

struct ContentView: View {
    @State private var counter = 0

    var body: some View {
        VStack {
            Image(systemName: "globe")
                .imageScale(.large)
                .foregroundStyle(.tint)
            Text("Test SwiftUI App")
            Text("Counter: \(counter)")
            Button("Increment") {
                counter += 1
                print("Button clicked! Counter is now: \(counter)")
            }
        }
        .padding()
        .onAppear {
            print("SwiftUI ContentView appeared")
        }
    }
}

#Preview {
    ContentView()
}
