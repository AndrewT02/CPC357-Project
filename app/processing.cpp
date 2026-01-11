#include <iostream>
#include <vector>
#include <string>
#include <cstdlib>
#include <fstream>

// --- CONSTANTS ---
const int WINDOW_SIZE = 10;
const int MOTION_HISTORY_SIZE = 60; // 2-3 mins of history
const int LDR_THRESHOLD_NIGHT = 800;
const int LDR_THRESHOLD_DAY = 600;

struct State {
    // Smoother
    int readings[WINDOW_SIZE];
    int index;
    long sum;
    
    // Hysteresis
    bool is_night;
    
    // Traffic Analytics
    int motion_history[MOTION_HISTORY_SIZE];
    int motion_index;
    int motion_sum; // Optimization: keep running sum
};

void load_state(State &s, const std::string &device_id) {
    std::string filename = "state_" + device_id + ".dat";
    std::ifstream in(filename, std::ios::binary);
    if (in) {
        in.read(reinterpret_cast<char*>(&s), sizeof(s));
    } else {
        // Init LDR
        for(int i=0; i<WINDOW_SIZE; i++) s.readings[i] = 0;
        s.index = 0;
        s.sum = 0;
        s.is_night = false;
        
        // Init Motion
        for(int i=0; i<MOTION_HISTORY_SIZE; i++) s.motion_history[i] = 0;
        s.motion_index = 0;
        s.motion_sum = 0;
    }
}

void save_state(const State &s, const std::string &device_id) {
    std::string filename = "state_" + device_id + ".dat";
    std::ofstream out(filename, std::ios::binary);
    out.write(reinterpret_cast<const char*>(&s), sizeof(s));
}

int main(int argc, char* argv[]) {
    // Usage: processing.exe process <device_id> <raw_ldr> <motion> <power>
    if (argc < 2) return 1;

    std::string command = argv[1];

    if (command == "process") {
        if (argc < 6) {
             std::cerr << "Usage: processing.exe process <device_id> <raw_ldr> <motion> <power>" << std::endl;
             return 1;
        }

        std::string device_id = argv[2];
        int raw_ldr = std::atoi(argv[3]);
        int motion = std::atoi(argv[4]);
        float power = std::atof(argv[5]);

        State s;
        load_state(s, device_id);

        // 1. Sliding Window (LDR)
        s.sum -= s.readings[s.index];
        s.readings[s.index] = raw_ldr;
        s.sum += raw_ldr;
        s.index = (s.index + 1) % WINDOW_SIZE;
        int smooth_ldr = s.sum / WINDOW_SIZE;

        // 2. Hysteresis
        if (smooth_ldr > LDR_THRESHOLD_NIGHT) s.is_night = true;
        else if (smooth_ldr < LDR_THRESHOLD_DAY) s.is_night = false;

        // 3. Traffic Analytics (Motion Intensity)
        s.motion_sum -= s.motion_history[s.motion_index];
        s.motion_history[s.motion_index] = motion;
        s.motion_sum += motion;
        s.motion_index = (s.motion_index + 1) % MOTION_HISTORY_SIZE;
        
        float traffic_intensity = ((float)s.motion_sum / MOTION_HISTORY_SIZE) * 100.0;

        // 4. Logic (Target Brightness Validation)
        int target_brightness = 0;
        if (s.is_night) {
             target_brightness = (motion > 0) ? 100 : 30;
        }

        // 5. Anomaly Detection
        int anomaly = 0;
        // Simple logic check: If target is High but Power is Low -> Blown Bulb
        if (target_brightness > 10 && power < 0.1) anomaly = 1; 
        // If target is Off but Power is High -> Leakage
        if (target_brightness == 0 && power > 1.0) anomaly = 2; 

        save_state(s, device_id);

        // Output JSON
        std::cout << "{\"smooth_ldr\": " << smooth_ldr
                  << ", \"is_night\": " << (s.is_night ? 1 : 0) 
                  << ", \"brightness\": " << target_brightness 
                  << ", \"traffic_intensity\": " << traffic_intensity
                  << ", \"anomaly\": " << anomaly << "}" << std::endl;
        
        return 0;
    }

    if (command == "reset") {
        if (argc < 3) return 1;
        std::string device_id = argv[2];
        
        // Overwrite with empty state
        State s;
        // Zero out
        for(int i=0; i<WINDOW_SIZE; i++) s.readings[i] = 0;
        s.index = 0; s.sum = 0; s.is_night = false;
        for(int i=0; i<MOTION_HISTORY_SIZE; i++) s.motion_history[i] = 0;
        s.motion_index = 0; s.motion_sum = 0;
        
        save_state(s, device_id);
        std::cout << "RESET_OK" << std::endl;
        return 0;
    }

    return 1;
}
