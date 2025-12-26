#include <iostream>
#include <vector>
#include <string>
#include <cstdlib>

// --- STATE FILE ---
// Since this is a CLI called repeatedly, we need to persist state (Sliding Window)
// For simplicity in this assignment, we will use a TEMP file to store the sliding window values.
// In a real production IPC, we'd use Named Pipes or Sockets.
// Here we will use a file "state.dat" in the same folder.

#include <fstream>

const int WINDOW_SIZE = 10;
const int LDR_THRESHOLD_NIGHT = 800;
const int LDR_THRESHOLD_DAY = 600;

struct State {
    int readings[WINDOW_SIZE];
    int index;
    long sum;
    bool is_night;
};

void load_state(State &s) {
    std::ifstream in("state.dat", std::ios::binary);
    if (in) {
        in.read(reinterpret_cast<char*>(&s), sizeof(s));
    } else {
        // Init
        for(int i=0; i<WINDOW_SIZE; i++) s.readings[i] = 0;
        s.index = 0;
        s.sum = 0;
        s.is_night = false;
    }
}

void save_state(const State &s) {
    std::ofstream out("state.dat", std::ios::binary);
    out.write(reinterpret_cast<const char*>(&s), sizeof(s));
}

int main(int argc, char* argv[]) {
    if (argc < 2) return 1;

    std::string command = argv[1];
    State s;
    load_state(s);

    if (command == "process") {
        // Usage: processing.exe process <raw_ldr> <motion> <power>
        int raw = std::atoi(argv[2]);
        int motion = std::atoi(argv[3]);
        float power = std::atof(argv[4]);

        // 1. Sliding Window
        s.sum -= s.readings[s.index];
        s.readings[s.index] = raw;
        s.sum += raw;
        s.index = (s.index + 1) % WINDOW_SIZE;
        int smooth = s.sum / WINDOW_SIZE;

        // 2. Hysteresis
        if (smooth > LDR_THRESHOLD_NIGHT) s.is_night = true;
        else if (smooth < LDR_THRESHOLD_DAY) s.is_night = false;

        // 3. Logic
        int target_brightness = 0;
        if (s.is_night) {
             target_brightness = (motion > 0) ? 100 : 30;
        }

        // 4. Anomaly
        int anomaly = 0;
        if (target_brightness > 10 && power < 0.1) anomaly = 1; // Blown Bulb
        if (target_brightness == 0 && power > 1.0) anomaly = 2; // Leak

        save_state(s);

        // Output JSON format using simple string concatenation
        std::cout << "{\"smooth_ldr\": " << smooth 
                  << ", \"is_night\": " << (s.is_night ? 1 : 0) 
                  << ", \"brightness\": " << target_brightness 
                  << ", \"anomaly\": " << anomaly << "}" << std::endl;
        
        return 0;
    }

    if (command == "reset") {
        // Clear state
        for(int i=0; i<WINDOW_SIZE; i++) s.readings[i] = 0;
        s.index = 0;
        s.sum = 0;
        s.is_night = false;
        save_state(s);
        std::cout << "RESET_OK" << std::endl;
        return 0;
    }

    return 1;
}
